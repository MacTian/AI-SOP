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
    "result": None,
    "model_path": None,
    "dataset_dir": None,
    "_stop_flag": False,
    "_thread": None,
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
    _train_state["logs"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
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
        # Auto-generate data.yaml
        classes = _detect_classes(labels_dir)
        # Detect if any label file has polygon format (>5 values per line)
        is_segmentation = _detect_segmentation(labels_dir)
        yaml_content = f"""# Auto-generated data.yaml
path: {dataset_dir}
train: images
val: images
nc: {len(classes)}
names: {classes}
"""
        if is_segmentation:
            yaml_content += "# Format: segmentation (polygon)\n"
        with open(data_yaml, "w") as f:
            f.write(yaml_content)

    # Count images
    image_count = sum(1 for _ in images_dir.rglob("*") if _.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))

    with _train_lock:
        _train_state["dataset_dir"] = str(dataset_dir)

    return {"status": "ok", "dataset_name": dataset_name, "image_count": image_count, "path": str(dataset_dir)}


def _detect_classes(labels_dir: Path) -> list:
    """Detect class IDs from label files (bbox or polygon format)."""
    classes = set()
    if labels_dir.exists():
        for f in labels_dir.rglob("*.txt"):
            if f.name == "classes.txt":
                continue
            with open(f) as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        try:
                            classes.add(int(parts[0]))
                        except ValueError:
                            pass
    return [str(i) for i in sorted(classes)] if classes else ["0"]


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
        _train_state["result"] = None
        _train_state["_stop_flag"] = False

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

        # Try to download pre-trained model from China mirror first
        model_path = _download_pretrained(model_name)

        _log(f"Loading model: {model_name}")
        model = YOLO(model_path)

        _log(f"Dataset: {dataset_dir}")
        _log(f"Config: epochs={epochs}, batch={batch}, imgsz={imgsz}, lr={lr}, device={device}")

        data_yaml = Path(dataset_dir) / "data.yaml"
        if not data_yaml.exists():
            for sub in Path(dataset_dir).iterdir():
                if sub.is_dir() and (sub / "data.yaml").exists():
                    data_yaml = sub / "data.yaml"
                    break

        output_dir = MODELS_DIR / f"{dataset_name}_{int(time.time())}"
        output_dir.mkdir(parents=True, exist_ok=True)

        with _train_lock:
            _train_state["status"] = "training"

        # Custom callback to capture metrics
        def on_epoch_end(trainer):
            if _stop_requested():
                trainer.stop = True
                return
            metrics = trainer.validator.metrics
            with _train_lock:
                _train_state["current_epoch"] = trainer.epoch + 1
                _train_state["latest_metrics"] = {
                    "box_loss": float(trainer.loss_items[0]) if trainer.loss_items is not None else None,
                    "cls_loss": float(trainer.loss_items[1]) if trainer.loss_items is not None else None,
                    "map50": float(metrics.map50) if hasattr(metrics, "map50") else None,
                    "map50_95": float(metrics.map50_95) if hasattr(metrics, "map50_95") else None,
                }
            _log(f"Epoch {trainer.epoch + 1}/{epochs}: "
                 f"box_loss={_train_state['latest_metrics']['box_loss']:.4f}, "
                 f"mAP50={_train_state['latest_metrics']['map50']:.4f}")

        model.add_callback("on_epoch_end", on_epoch_end)

        _log("Starting training...")
        t0 = time.time()

        results = model.train(
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
        )

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

        _log(f"Training completed in {elapsed:.0f}s")
        _log(f"Final mAP50: {_train_state['result']['map50']:.4f}")

    except Exception as e:
        logger.exception("Training failed")
        with _train_lock:
            _train_state["status"] = "error"
            _train_state["logs"].append(f"[ERROR] {str(e)}")
        _log(f"Training failed: {e}")


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
async def get_training_status():
    """Get current training status and metrics."""
    with _train_lock:
        return {
            "status": _train_state["status"],
            "current_epoch": _train_state["current_epoch"],
            "total_epochs": _train_state["total_epochs"],
            "latest_metrics": _train_state["latest_metrics"],
            "logs": _train_state["logs"][-50:],  # Last 50 lines
            "result": _train_state["result"],
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
