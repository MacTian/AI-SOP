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
_multi_camera = None

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


def set_multi_camera(multi_camera):
    global _multi_camera
    _multi_camera = multi_camera


def _make_placeholder_frame(width=640, height=480, text="No Camera"):
    """Generate a placeholder JPEG frame when camera is unavailable."""
    import cv2
    import numpy as np
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Dark gray background
    frame[:] = (40, 40, 40)
    # Draw text
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(text, font, 1.0, 2)[0]
    x = (width - text_size[0]) // 2
    y = (height + text_size[1]) // 2
    cv2.putText(frame, text, (x, y), font, 1.0, (180, 180, 180), 2)
    # Draw camera icon hint
    hint = "Check camera connection"
    hint_size = cv2.getTextSize(hint, font, 0.5, 1)[0]
    hx = (width - hint_size[0]) // 2
    cv2.putText(frame, hint, (hx, y + 40), font, 0.5, (120, 120, 120), 1)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


async def generate_mjpeg():
    """Generate MJPEG stream with detection boxes overlaid."""
    import cv2

    no_cam_sent = False
    while True:
        if _capture is None or not _capture.is_running:
            # Send a placeholder frame so the browser <img> tag gets data
            jpeg_bytes = _make_placeholder_frame(text="Camera Unavailable")
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
            no_cam_sent = True
            await asyncio.sleep(1.0)
            continue

        no_cam_sent = False

        # Prefer annotated frame (with detection boxes)
        frame = None
        if _inference_engine:
            frame = _inference_engine.get_annotated_frame()

        # Fallback to raw preprocessed frame
        if frame is None:
            raw = _capture.get_frame()
            if raw is None:
                # Camera running but no frame yet — send placeholder
                jpeg_bytes = _make_placeholder_frame(text="Waiting for camera...")
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
                await asyncio.sleep(0.2)
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


@router.get("/video/cameras")
async def list_cameras():
    """List active cameras in multi-camera mode."""
    if _multi_camera is None:
        return {"cameras": [], "mode": "single"}
    return {
        "cameras": _multi_camera.get_active_cameras(),
        "mode": "multi",
    }


@router.get("/video/stream/{camera_id}")
async def video_stream_camera(camera_id: int):
    """MJPEG stream for a specific camera in multi-camera mode."""
    if _multi_camera is None:
        return {"error": "Multi-camera mode not active"}

    async def generate():
        import cv2
        while True:
            frame = _multi_camera.get_frame(camera_id)
            if frame is None:
                await asyncio.sleep(0.5)
                continue
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
            await asyncio.sleep(1.0 / 15)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
