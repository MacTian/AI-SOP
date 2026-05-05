"""Camera capture thread using OpenCV."""

import threading
import time
import logging

import cv2
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


class CameraCapture:
    """Threaded camera capture using OpenCV.

    Continuously reads frames from the camera in a background thread.
    Latest frame is always available via `get_frame()`.
    """

    def __init__(self, device: int | None = None):
        self._device = device if device is not None else settings.camera_device
        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Open camera and start capture thread."""
        if self._running:
            logger.warning("Camera capture already running")
            return True

        self._cap = cv2.VideoCapture(self._device)
        if not self._cap.isOpened():
            # Try alternate device
            alt = 1 if self._device == 0 else 0
            logger.warning(f"Cannot open /dev/video{self._device}, trying /dev/video{alt}")
            self._cap = cv2.VideoCapture(alt)
            if not self._cap.isOpened():
                logger.error("Cannot open any camera device")
                return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
        self._cap.set(cv2.CAP_PROP_FPS, settings.camera_fps)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Camera capture started on /dev/video{self._device}")
        return True

    def stop(self):
        """Stop capture thread and release camera."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Camera capture stopped")

    def get_frame(self) -> np.ndarray | None:
        """Return the most recent captured frame (thread-safe copy)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def is_running(self) -> bool:
        return self._running

    def _capture_loop(self):
        """Background loop: read frames at configured FPS."""
        import numpy as np
        interval = 1.0 / settings.camera_fps
        fail_count = 0
        max_fails = 10  # After 10 consecutive failures, mark as not running
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                fail_count += 1
                if fail_count == max_fails:
                    logger.error(f"Camera failed {fail_count} consecutive reads — stopping capture")
                    self._running = False
                    break
                elif fail_count % 5 == 0:
                    logger.warning(f"Camera read failed {fail_count} times...")
                time.sleep(0.1)
                continue
            fail_count = 0  # Reset on success
            with self._lock:
                self._frame = frame
            time.sleep(interval)
