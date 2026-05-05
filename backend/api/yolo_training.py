"""YOLO model training API: upload dataset, train, download model."""

import json
import logging
import os
import shutil
import threading
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/training/yolo", tags=["YOLO Training"], dependencies=[Depends(get_current_user)])

# Training state (thread-safe via lock)
_train_lock = threading.Lock()
_train_state = {
    "status": "idle",  # idle | downloading | training | completed | stopped | error
    "current_epoch": 0,
    "total_epochs": 0,
    "latest_metrics": None,
    "logs": [],
    "log_count": 0,       # total lines ever logged (for offset tracking)
    "result": None,
    "model_path": None,
    "dataset_dir": None,
    "_stop_flag": False,
    "_thread": None,
    "_last_progress_time": None,  # timestamp of last epoch / log activity
    "_start_time": None,
    "_warnings": [],       # stall / issue hints for the frontend
}

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATASETS_DIR = BASE_DIR / "datasets"
MODELS_DIR = BASE_DIR / "trained_models"
DATASETS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# China mirror for Ultralytics models
CHINA_MIRROR = "https://pypi.tuna.tsinghua.edu.cn"
ULTRALYTICS_MIRROR = "https://ghfast.top/https://github.com"


def _log(msg: str):
    ts = time.strftime('%H:%M:%S')
    _train_state["logs"].append(f"[{ts}] {msg}")
    _train_state["log_count"] = len(_train_state["logs"])
    _train_state["_last_progress_time"] = time.time()
    logger.info(msg)


def _stop_requested():
    return _train_state["_stop_flag"]


@router.post("/dataset/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Form("sop_dataset"),
):
    """Upload a YOLO-format dataset as ZIP file."""
    dataset_dir = DATASETS_DIR / dataset_name
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)

    # Save and extract ZIP
    zip_path = DATASETS_DIR / f"{dataset_name}.zip"
    content = await file.read()
    with open(zip_path, "wb") as f:
        f.write(content)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dataset_dir)
        zip_path.unlink()  # Remove zip after extraction
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")

    # Validate dataset structure
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"
    data_yaml = dataset_dir / "data.yaml"

    if not images_dir.exists():
        # Maybe images are in subdirectories
        for sub in dataset_dir.iterdir():
            if sub.is_dir() and (sub / "images").exists():
                images_dir = sub / "images"
                labels_dir = sub / "labels"
                data_yaml = sub / "data.yaml"
                break

    if not images_dir.exists():
        raise HTTPException(status_code=400, detail="Dataset must contain an 'images/' directory")

    if not data_yaml.exists():
        # Auto-generate data.yaml with proper class detection
        names, needs_remap = _detect_classes(dataset_dir, labels_dir)
        is_segmentation = _detect_segmentation(labels_dir)

        # Build YAML content with proper formatting
        names_str = ", ".join(f"'{n}'" for n in names)
        yaml_content = f"""# Auto-generated data.yaml
path: {dataset_dir}
train: images
val: images
nc: {len(names)}
names: [{names_str}]
"""
        if is_segmentation:
            yaml_content += "# Format: segmentation (polygon)\n"
        if needs_remap:
            yaml_content += f"# WARNING: Label class IDs are not 0-indexed — will be remapped during training\n"
        with open(data_yaml, "w") as f:
            f.write(yaml_content)

    # Count images
    image_count = sum(1 for _ in images_dir.rglob("*") if _.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))

    with _train_lock:
        _train_state["dataset_dir"] = str(dataset_dir)

    return {"status": "ok", "dataset_name": dataset_name, "image_count": image_count, "path": str(dataset_dir)}


def _load_classes_txt(dataset_dir: Path) -> list | None:
    """Load class names from classes.txt if it exists.
    Returns list of names, or None if not found.
    """
    for path in [dataset_dir / "classes.txt", dataset_dir / "labels" / "classes.txt"]:
        if path.exists():
            names = []
            with open(path) as f:
                for line in f:
                    name = line.strip()
                    if name:
                        names.append(name)
            return names if names else None
    return None


def _detect_classes(dataset_dir: Path, labels_dir: Path) -> tuple[list, bool]:
    """Detect class names and whether remapping is needed.

    Returns (names, needs_remap):
      - names: list of class name strings indexed by class ID
      - needs_remap: True if label IDs don't start at 0 or have gaps

    Strategy:
      1. If classes.txt exists, use it as the authoritative source.
      2. Otherwise, derive from label file IDs.
      3. Detect if label IDs need remapping to 0-indexed.
    """
    # Try classes.txt first
    names_from_file = _load_classes_txt(dataset_dir)
    if names_from_file:
        names = names_from_file
    else:
        # Derive from label file IDs
        ids = set()
        if labels_dir.exists():
            for f in labels_dir.rglob("*.txt"):
                if f.name == "classes.txt":
                    continue
                with open(f) as fh:
                    for line in fh:
                        parts = line.strip().split()
                        if parts:
                            try:
                                ids.add(int(parts[0]))
                            except ValueError:
                                pass
        names = [str(i) for i in sorted(ids)] if ids else ["0"]

    # Find the actual max class ID used in labels
    max_id = len(names) - 1
    if labels_dir.exists():
        for f in labels_dir.rglob("*.txt"):
            if f.name == "classes.txt":
                continue
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        try:
                            cid = int(parts[0])
                            if cid > max_id:
                                max_id = cid
                        except ValueError:
                            pass

    # Extend names list if label IDs exceed current names
    if max_id >= len(names):
        names = names + [str(i) for i in range(len(names), max_id + 1)]

    # Check if remapping is needed (IDs don't start at 0 or have gaps)
    ids_set = set()
    if labels_dir.exists():
        for f in labels_dir.rglob("*.txt"):
            if f.name == "classes.txt":
                continue
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        try:
                            ids_set.add(int(parts[0]))
                        except ValueError:
                            pass

    needs_remap = bool(ids_set) and (min(ids_set) != 0 or len(ids_set) != (max(ids_set) + 1))

    return names, needs_remap


def _detect_segmentation(labels_dir: Path) -> bool:
    """Detect if label files contain polygon segmentation data.
    Polygon lines have > 5 values (class + 3+ coordinate pairs).
    BBox lines have exactly 5 values (class + cx + cy + w + h).
    """
    if not labels_dir.exists():
        return False
    for f in labels_dir.rglob("*.txt"):
        if f.name == "classes.txt":
            continue
        with open(f) as fh:
            for line in fh:
                parts = line.strip().split()
                if len(parts) > 5:
                    return True
    return False


@router.post("/start")
async def start_training(config: dict):
    """Start YOLO model training."""
    with _train_lock:
        if _train_state["status"] == "training":
            raise HTTPException(status_code=400, detail="Training already in progress")

        dataset_dir = _train_state.get("dataset_dir")
        if not dataset_dir or not Path(dataset_dir).exists():
            raise HTTPException(status_code=400, detail="No dataset uploaded")

        # Reset state
        _train_state["status"] = "downloading"
        _train_state["current_epoch"] = 0
        _train_state["total_epochs"] = config.get("epochs", 50)
        _train_state["latest_metrics"] = None
        _train_state["logs"] = []
        _train_state["log_count"] = 0
        _train_state["result"] = None
        _train_state["_stop_flag"] = False
        _train_state["_last_progress_time"] = time.time()
        _train_state["_start_time"] = time.time()
        _train_state["_warnings"] = []

    # Start training in background thread
    thread = threading.Thread(target=_run_training, args=(config, dataset_dir), daemon=True)
    _train_state["_thread"] = thread
    thread.start()

    return {"status": "started"}


def _get_device(requested_device: str) -> str:
    """Resolve training device with auto-detection and fallback.
    Returns a valid device string for ultralytics.
    """
    import torch

    if requested_device == "cpu":
        _log("Device: CPU (user selected)")
        return "cpu"

    # User requested GPU — check availability
    if not torch.cuda.is_available():
        _log("WARNING: CUDA not available, falling back to CPU")
        return "cpu"

    # Parse device index
    try:
        device_idx = int(requested_device)
    except (ValueError, TypeError):
        device_idx = 0

    gpu_count = torch.cuda.device_count()
    if device_idx >= gpu_count:
        _log(f"WARNING: GPU {device_idx} not found ({gpu_count} GPU(s)), using GPU 0")
        device_idx = 0

    gpu_name = torch.cuda.get_device_name(device_idx)
    gpu_mem = torch.cuda.get_device_properties(device_idx).total_memory // (1024**3)
    _log(f"Device: GPU {device_idx} — {gpu_name} ({gpu_mem} GB)")
    return str(device_idx)


def _remap_labels_if_needed(dataset_dir: Path, data_yaml: Path) -> Path:
    """Remap label class IDs to 0-indexed contiguous range if needed.

    YOLO requires class IDs to be 0, 1, ..., nc-1. If labels use non-contiguous
    or non-zero-starting IDs (e.g. 5,6,7,8,9), this creates a remapped copy.

    Returns the path to the (possibly remapped) label directory.
    """
    labels_dir = dataset_dir / "labels"
    if not labels_dir.exists():
        return labels_dir

    # Collect all class IDs
    all_ids = set()
    label_files = []
    for f in labels_dir.rglob("*.txt"):
        if f.name == "classes.txt":
            continue
        if f.is_file():
            label_files.append(f)
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        try:
                            all_ids.add(int(parts[0]))
                        except ValueError:
                            pass

    if not all_ids:
        return labels_dir

    sorted_ids = sorted(all_ids)
    # Check if already 0-indexed contiguous
    if sorted_ids[0] == 0 and len(sorted_ids) == sorted_ids[-1] + 1:
        return labels_dir  # No remapping needed

    # Build remapping: old_id -> new_id
    id_map = {old: new for new, old in enumerate(sorted_ids)}
    _log(f"Remapping class IDs: {id_map}")

    # Backup original labels, then replace in-place with remapped IDs
    backup_dir = dataset_dir / "_labels_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(labels_dir, backup_dir)
    _log(f"Backed up original labels to: {backup_dir}")

    remapped_count = 0
    for f in label_files:
        lines = []
        with open(f) as fh:
            for line in fh:
                parts = line.strip().split()
                if parts:
                    try:
                        old_id = int(parts[0])
                        parts[0] = str(id_map[old_id])
                        lines.append(" ".join(parts) + "\n")
                        remapped_count += 1
                    except (ValueError, KeyError):
                        lines.append(line)
                else:
                    lines.append(line)
        with open(f, "w") as oh:
            oh.writelines(lines)

    _log(f"Remapped {remapped_count} label entries across {len(label_files)} files (in-place)")

    # Update data.yaml: fix nc and names to match new 0-indexed IDs
    if data_yaml.exists():
        import yaml
        with open(data_yaml) as f:
            ydata = yaml.safe_load(f)
        ydata["nc"] = len(sorted_ids)

        # Get real class names: prefer classes.txt, fallback to data.yaml names
        real_names = _load_classes_txt(dataset_dir)
        orig_names = ydata.get("names", [])

        new_names = [""] * len(sorted_ids)
        for old_id, new_id in id_map.items():
            if real_names and old_id < len(real_names):
                # Use real name from classes.txt
                new_names[new_id] = real_names[old_id]
            elif isinstance(orig_names, list) and old_id < len(orig_names):
                new_names[new_id] = orig_names[old_id]
            else:
                new_names[new_id] = str(old_id)
        ydata["names"] = new_names
        ydata["path"] = str(dataset_dir)
        with open(data_yaml, "w") as f:
            yaml.dump(ydata, f, default_flow_style=False, allow_unicode=True)
        _log(f"Updated data.yaml: nc={len(sorted_ids)}, names={ydata.get('names', [])}")

    return labels_dir


def _run_training(config: dict, dataset_dir: str):
    """Run YOLO training in background thread."""
    try:
        from ultralytics import YOLO

        model_name = config.get("model", "yolov8n.pt")
        epochs = config.get("epochs", 50)
        batch = config.get("batch", 16)
        imgsz = config.get("imgsz", 640)
        lr = config.get("lr", 0.01)
        dataset_name = config.get("dataset_name", "sop_dataset")

        # Resolve device with auto-detection
        device = _get_device(config.get("device", "cpu"))
        use_gpu = device != "cpu"

        # Auto-tune batch size for GPU: scale up for better utilization
        # but cap to avoid OOM on smaller GPUs
        if use_gpu:
            import torch
            gpu_mem_gb = torch.cuda.get_device_properties(int(device)).total_memory / (1024**3)
            if batch <= 16 and gpu_mem_gb >= 8:
                auto_batch = min(32, max(16, int(gpu_mem_gb * 2.5)))
                _log(f"Auto-tuning batch: {batch} → {auto_batch} (GPU has {gpu_mem_gb:.0f} GB)")
                batch = auto_batch

        # Try to download pre-trained model from China mirror first
        model_path = _download_pretrained(model_name)

        _log(f"Loading model: {model_name}")
        model = YOLO(model_path)

        _log(f"Dataset: {dataset_dir}")
        _log(f"Config: epochs={epochs}, batch={batch}, imgsz={imgsz}, lr={lr}, device={device}")

        # Count images for info
        images_dir = Path(dataset_dir) / "images"
        if images_dir.exists():
            img_count = sum(1 for _ in images_dir.rglob("*") if _.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
            _log(f"Training images found: {img_count}")
            if img_count == 0:
                _log("WARNING: No images found in dataset — training will fail")

        data_yaml = Path(dataset_dir) / "data.yaml"
        if not data_yaml.exists():
            for sub in Path(dataset_dir).iterdir():
                if sub.is_dir() and (sub / "data.yaml").exists():
                    data_yaml = sub / "data.yaml"
                    break

        if not data_yaml.exists():
            raise FileNotFoundError(f"data.yaml not found in {dataset_dir}")

        # Remap label class IDs if they're not 0-indexed contiguous
        _remap_labels_if_needed(Path(dataset_dir), data_yaml)

        output_dir = MODELS_DIR / f"{dataset_name}_{int(time.time())}"
        output_dir.mkdir(parents=True, exist_ok=True)

        with _train_lock:
            _train_state["status"] = "training"

        # Custom callback to capture metrics after each epoch
        epoch_start_time = [time.time()]

        def on_epoch_start(trainer):
            epoch_start_time[0] = time.time()

        def on_epoch_end(trainer):
            if _stop_requested():
                trainer.stop = True
                return
            epoch_elapsed = time.time() - epoch_start_time[0]
            metrics = trainer.validator.metrics
            with _train_lock:
                _train_state["current_epoch"] = trainer.epoch + 1
                _train_state["latest_metrics"] = {
                    "box_loss": float(trainer.loss_items[0]) if trainer.loss_items is not None else None,
                    "cls_loss": float(trainer.loss_items[1]) if trainer.loss_items is not None else None,
                    "dfl_loss": float(trainer.loss_items[2]) if trainer.loss_items is not None and len(trainer.loss_items) > 2 else None,
                    "map50": float(metrics.map50) if hasattr(metrics, "map50") else None,
                    "map50_95": float(metrics.map50_95) if hasattr(metrics, "map50_95") else None,
                }
            m = _train_state['latest_metrics']
            _log(f"Epoch {trainer.epoch + 1}/{epochs} ({epoch_elapsed:.0f}s): "
                 f"box_loss={m['box_loss']:.4f} cls_loss={m['cls_loss']:.4f} "
                 f"mAP50={m['map50']:.4f} mAP50-95={m['map50_95']:.4f}")

        model.add_callback("on_epoch_start", on_epoch_start)
        model.add_callback("on_epoch_end", on_epoch_end)

        _log("Starting training...")
        t0 = time.time()

        # Build training kwargs — enable workers and AMP for GPU
        train_kwargs = dict(
            data=str(data_yaml),
            epochs=epochs,
            batch=batch,
            imgsz=imgsz,
            lr0=lr,
            device=device,
            project=str(output_dir),
            name="train",
            exist_ok=True,
            verbose=False,
            # Performance settings
            workers=4 if use_gpu else 0,
            amp=use_gpu,          # Automatic Mixed Precision — faster on GPU
            cache="ram" if use_gpu else False,  # Cache images in RAM for faster loading
            patience=50,          # early stopping patience
        )

        results = model.train(**train_kwargs)

        elapsed = time.time() - t0

        if _stop_requested():
            _log("Training stopped by user")
            with _train_lock:
                _train_state["status"] = "stopped"
            return

        # Save best model path
        best_model = Path(results.save_dir) / "weights" / "best.pt"
        if best_model.exists():
            final_path = MODELS_DIR / f"{dataset_name}_best.pt"
            shutil.copy2(best_model, final_path)
            _log(f"Model saved: {final_path}")

        with _train_lock:
            _train_state["status"] = "completed"
            _train_state["model_path"] = str(final_path) if best_model.exists() else None
            _train_state["result"] = {
                "map50": float(results.results_dict.get("metrics/mAP50(B)", 0)),
                "map50_95": float(results.results_dict.get("metrics/mAP50-95(B)", 0)),
                "elapsed": round(elapsed, 1),
                "model_path": str(final_path) if best_model.exists() else None,
            }

        _log(f"Training completed in {elapsed:.0f}s ({elapsed / max(epochs, 1):.1f}s/epoch)")
        _log(f"Final mAP50: {_train_state['result']['map50']:.4f}")

    except Exception as e:
        logger.exception("Training failed")
        err_msg = str(e)
        with _train_lock:
            _train_state["status"] = "error"
            _train_state["_warnings"].append(f"Error: {err_msg}")
        _log(f"Training failed: {err_msg}")
        # Provide actionable hints for common errors
        if "CUDA out of memory" in err_msg:
            _log("HINT: Try reducing batch size or image size")
        elif "No labels found" in err_msg or "No images found" in err_msg:
            _log("HINT: Check dataset structure — need images/ and labels/ directories")
        elif "not enough memory" in err_msg.lower():
            _log("HINT: Close other applications or reduce batch size")


def _download_pretrained(model_name: str) -> str:
    """Try to download pre-trained model from China mirror first, fallback to default."""
    model_path = BASE_DIR / "models" / model_name
    if model_path.exists():
        return str(model_path)

    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Try China mirror first
    china_url = f"https://ghfast.top/https://github.com/ultralytics/assets/releases/download/v8.3.0/{model_name}"
    try:
        _log(f"Downloading {model_name} from China mirror...")
        import urllib.request
        urllib.request.urlretrieve(china_url, str(model_path))
        _log(f"Downloaded from China mirror: {model_name}")
        return str(model_path)
    except Exception as e:
        _log(f"China mirror failed ({e}), using default Ultralytics download...")

    # Fallback: let ultralytics handle it
    return model_name


@router.get("/gpu-info")
async def get_gpu_info():
    """Get GPU availability and info for the training UI."""
    import torch
    info = {
        "cuda_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "gpus": [],
    }
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            info["gpus"].append({
                "index": i,
                "name": props.name,
                "memory_gb": round(props.total_memory / (1024**3), 1),
                "compute_capability": f"{props.major}.{props.minor}",
            })
    return info


@router.get("/status")
async def get_training_status(offset: int = 0):
    """Get current training status and metrics.
    offset: return only log lines after this index (for deduplication).
    """
    import time as _time
    with _train_lock:
        all_logs = _train_state["logs"]
        total = len(all_logs)
        # Return only new lines since offset
        if offset < total:
            new_logs = all_logs[offset:]
        else:
            new_logs = []

        # Auto-detect stalls: if training and no progress for 120s
        warnings = list(_train_state["_warnings"])
        elapsed_total = None
        if _train_state["_start_time"]:
            elapsed_total = round(_time.time() - _train_state["_start_time"], 1)

        if _train_state["status"] == "training" and _train_state["_last_progress_time"]:
            idle_seconds = _time.time() - _train_state["_last_progress_time"]
            if idle_seconds > 120:
                stall_msg = f"No progress for {int(idle_seconds)}s — training may be stuck (check GPU memory / data loading)"
                if stall_msg not in warnings:
                    warnings.append(stall_msg)
            elif idle_seconds > 60:
                slow_msg = f"Slow progress — last update {int(idle_seconds)}s ago"
                if slow_msg not in warnings:
                    warnings.append(slow_msg)

        return {
            "status": _train_state["status"],
            "current_epoch": _train_state["current_epoch"],
            "total_epochs": _train_state["total_epochs"],
            "latest_metrics": _train_state["latest_metrics"],
            "logs": new_logs,
            "log_offset": offset,
            "log_total": total,
            "result": _train_state["result"],
            "warnings": warnings,
            "elapsed": elapsed_total,
        }


@router.post("/stop")
async def stop_training():
    """Stop ongoing training."""
    with _train_lock:
        _train_state["_stop_flag"] = True
    return {"status": "stopping"}


@router.get("/download")
async def download_model():
    """Download the trained model."""
    with _train_lock:
        path = _train_state.get("model_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="No trained model available")
    return FileResponse(path, filename=Path(path).name)


@router.post("/use")
async def use_trained_model():
    """Set the trained model as the active detection model."""
    with _train_lock:
        path = _train_state.get("model_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="No trained model available")

    # Update global detector
    from backend.api.labeling import _detector
    if _detector is not None:
        _detector.load_model(path)

    return {"status": "ok", "model_path": path}
