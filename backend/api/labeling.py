"""YOLO data labeling API: auto-label images using YOLO detection."""

import io
import logging
import zipfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse

from backend.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/label", tags=["Labeling"], dependencies=[Depends(get_current_user)])

# Will be set by main.py
_detector = None


def set_detector(detector):
    global _detector
    _detector = detector


@router.post("/auto")
async def auto_label(file: UploadFile = File(...)):
    """Upload an image and return YOLO auto-detection results as labeling suggestions."""
    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialized")

    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    results = _detector.detect(img)
    h, w = img.shape[:2]

    detections = []
    for det in results.detections:
        x1, y1, x2, y2 = det.bbox
        detections.append({
            "cls": det.class_name,
            "conf": det.confidence,
            "type": "box",
            "x": ((x1 + x2) / 2) / w,
            "y": ((y1 + y2) / 2) / h,
            "w": (x2 - x1) / w,
            "h": (y2 - y1) / h,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "img_w": w, "img_h": h,
        })

    return {"detections": detections, "image_size": {"width": w, "height": h}}


@router.post("/batch")
async def batch_label(files: list[UploadFile] = File(...)):
    """Batch auto-label multiple images."""
    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialized")

    results = []
    for file in files:
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            results.append({"filename": file.filename, "error": "Invalid image"})
            continue

        det_result = _detector.detect(img)
        h, w = img.shape[:2]
        results.append({
            "filename": file.filename,
            "detections": [
                {
                    "cls": d.class_name,
                    "conf": d.confidence,
                    "type": "box",
                    "x": ((d.bbox[0] + d.bbox[2]) / 2) / w,
                    "y": ((d.bbox[1] + d.bbox[3]) / 2) / h,
                    "w": (d.bbox[2] - d.bbox[0]) / w,
                    "h": (d.bbox[3] - d.bbox[1]) / h,
                }
                for d in det_result.detections
            ],
        })

    return {"results": results}
