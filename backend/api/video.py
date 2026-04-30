"""MJPEG video streaming endpoint with detection overlay."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Video"])

# Will be set by main.py
_capture = None
_preprocessor = None
_inference_engine = None

SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots"


def set_capture(capture):
    global _capture
    _capture = capture


def set_preprocessor(preprocessor):
    global _preprocessor
    _preprocessor = preprocessor


def set_inference_engine(engine):
    global _inference_engine
    _inference_engine = engine


async def generate_mjpeg():
    """Generate MJPEG stream with detection boxes overlaid."""
    import cv2

    while True:
        if _capture is None or not _capture.is_running:
            await asyncio.sleep(0.5)
            continue

        # Prefer annotated frame (with detection boxes)
        frame = None
        if _inference_engine:
            frame = _inference_engine.get_annotated_frame()

        # Fallback to raw preprocessed frame
        if frame is None:
            raw = _capture.get_frame()
            if raw is None:
                await asyncio.sleep(0.1)
                continue
            if _preprocessor:
                frame = _preprocessor.process(raw)
            else:
                frame = raw

        # Encode to JPEG
        if _preprocessor:
            jpeg_bytes = _preprocessor.to_jpeg(frame)
        else:
            _, buf = cv2.imencode(".jpg", frame)
            jpeg_bytes = buf.tobytes()

        if jpeg_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )

        await asyncio.sleep(1.0 / 15)  # ~15 fps stream


@router.get("/video/stream")
async def video_stream():
    """MJPEG video stream endpoint. Viewable in browser <img> tag."""
    return StreamingResponse(
        generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/video/snapshot")
async def video_snapshot():
    """Get a single JPEG snapshot with detection boxes."""
    from fastapi.responses import Response

    if _capture is None or not _capture.is_running:
        return {"error": "Camera not available"}

    # Prefer annotated frame
    frame = None
    if _inference_engine:
        frame = _inference_engine.get_annotated_frame()

    if frame is None:
        raw = _capture.get_frame()
        if raw is None:
            return {"error": "No frame available"}
        if _preprocessor:
            frame = _preprocessor.process(raw)
        else:
            frame = raw

    jpeg_bytes = _preprocessor.to_jpeg(frame) if _preprocessor else b""
    return Response(content=jpeg_bytes, media_type="image/jpeg")


def save_screenshot(sop_id: str, step_id: str, event_status: str) -> str | None:
    """Save the current annotated frame as a screenshot.

    Returns the relative file path if saved, None otherwise.
    """
    if _inference_engine is None:
        return None

    frame = _inference_engine.get_annotated_frame()
    if frame is None:
        return None

    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{sop_id}_{step_id}_{event_status}_{ts}.jpg"
        filepath = SCREENSHOTS_DIR / filename

        if _preprocessor:
            jpeg_bytes = _preprocessor.to_jpeg(frame)
        else:
            import cv2
            _, buf = cv2.imencode(".jpg", frame)
            jpeg_bytes = buf.tobytes()

        filepath.write_bytes(jpeg_bytes)
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")
        return None


@router.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """Serve a saved screenshot image."""
    from fastapi.responses import Response

    filepath = SCREENSHOTS_DIR / filename
    if not filepath.exists():
        return {"error": "Screenshot not found"}
    return Response(content=filepath.read_bytes(), media_type="image/jpeg")
