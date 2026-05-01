"""Image preprocessing utilities."""

import cv2
import numpy as np

from backend.config import settings


class ImagePreprocessor:
    """Handles frame preprocessing: resize, ROI extraction, normalization."""

    def __init__(self, target_size: tuple[int, int] = (640, 480)):
        self.target_size = target_size
        self._roi: tuple[int, int, int, int] | None = None  # (x, y, w, h)

    def set_roi(self, x: int, y: int, w: int, h: int):
        """Set region of interest (x, y, width, height)."""
        self._roi = (x, y, w, h)

    def clear_roi(self):
        """Remove ROI, use full frame."""
        self._roi = None

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Full preprocessing pipeline: crop ROI → resize → normalize."""
        if frame is None:
            return np.zeros((*self.target_size[::-1], 3), dtype=np.uint8)

        result = frame

        # 1. Apply ROI if set
        if self._roi:
            x, y, w, h = self._roi
            result = result[y:y + h, x:x + w]

        # 2. Resize to target
        result = cv2.resize(result, self.target_size)

        return result

    def to_jpeg(self, frame: np.ndarray, quality: int = 80) -> bytes:
        """Encode frame as JPEG bytes for streaming."""
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes()
