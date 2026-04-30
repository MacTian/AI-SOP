"""Video file analysis: upload a video and run SOP detection on its frames."""

import asyncio
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["Video Analysis"])

# Will be set by main.py
_detector = None
_preprocessor = None
_rule_engine = None
_sop_manager = None


def set_detector(detector):
    global _detector
    _detector = detector


def set_preprocessor(preprocessor):
    global _preprocessor
    _preprocessor = preprocessor


def set_rule_engine(rule_engine):
    global _rule_engine
    _rule_engine = rule_engine


def set_sop_manager(sop_manager):
    global _sop_manager
    _sop_manager = sop_manager


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    sop_id: str | None = None,
    sample_fps: float = 2.0,
    max_frames: int = 500,
):
    """Upload a video file and analyze it against SOP rules.

    Args:
        file: Video file (mp4, avi, etc.)
        sop_id: Specific SOP to check against (None = all SOPs)
        sample_fps: Frames per second to sample (default 2)
        max_frames: Maximum frames to process
    """
    if _detector is None:
        return {"error": "Detector not initialized"}

    import cv2
    import numpy as np

    # Save uploaded file to temp
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return {"error": "Failed to open video file"}

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0
        frame_interval = max(1, int(video_fps / sample_fps))

        # Determine which SOPs to check
        sop_ids = []
        if sop_id:
            sop_ids = [sop_id]
        elif _sop_manager:
            sop_ids = [s["sop_id"] for s in _sop_manager.list_sops()]

        # Load rules for target SOPs
        step_rules_map = {}
        if _rule_engine and _sop_manager:
            for sid in sop_ids:
                try:
                    sop = _sop_manager.load(sid)
                    step_rules_map[sid] = [
                        {
                            "step_id": step.step_id,
                            "step_name": step.name,
                            "expected_objects": step.rule.expected_objects,
                            "min_confidence": step.rule.min_confidence,
                            "required_count": step.rule.required_count,
                        }
                        for step in sop.steps
                    ]
                except Exception:
                    pass

        # Process frames
        detections_log = []
        frame_idx = 0
        processed_count = 0

        _detector.load_model()

        while cap.isOpened() and processed_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                # Preprocess
                if _preprocessor:
                    processed = _preprocessor.process(frame)
                else:
                    processed = frame

                # Detect
                result = _detector.detect(processed)

                # Check against rules
                frame_detections = []
                for sid, rules in step_rules_map.items():
                    for rule in rules:
                        expected = set(rule["expected_objects"])
                        min_conf = rule["min_confidence"]
                        required = rule["required_count"]

                        matching = [
                            d for d in result.detections
                            if d.class_name in expected and d.confidence >= min_conf
                        ]

                        if len(matching) >= required:
                            frame_detections.append({
                                "sop_id": sid,
                                "step_id": rule["step_id"],
                                "step_name": rule["step_name"],
                                "matched_objects": [d.class_name for d in matching],
                                "avg_confidence": round(
                                    sum(d.confidence for d in matching) / len(matching), 3
                                ),
                            })

                if frame_detections:
                    timestamp = frame_idx / video_fps if video_fps > 0 else 0
                    detections_log.append({
                        "frame": frame_idx,
                        "timestamp": round(timestamp, 2),
                        "detections": frame_detections,
                    })

                processed_count += 1

            frame_idx += 1

        cap.release()

        return {
            "video_info": {
                "filename": file.filename,
                "duration": round(duration, 2),
                "fps": video_fps,
                "total_frames": total_frames,
                "sampled_frames": processed_count,
            },
            "sops_checked": sop_ids,
            "matching_events": len(detections_log),
            "timeline": detections_log,
        }

    finally:
        Path(tmp_path).unlink(missing_ok=True)
