"""Inference engine: orchestrates capture → preprocess → detect pipeline."""

import threading
import time
import logging

import numpy as np

from backend.config import settings
from backend.camera.capture import CameraCapture
from backend.camera.preprocessor import ImagePreprocessor
from backend.inference.detector import Detector, DetectionResult

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Orchestrates the frame processing pipeline.

    Runs detection at a configured interval on the latest camera frame.
    Results are available via `get_latest_result()` and a callback.
    """

    def __init__(self, camera: CameraCapture, detector: Detector | None = None):
        self.camera = camera
        self.preprocessor = ImagePreprocessor()
        self.detector = detector or Detector()

        self._latest_frame: np.ndarray | None = None
        self._latest_result: DetectionResult | None = None
        self._latest_processed_frame: np.ndarray | None = None
        self._latest_annotated_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_result_callback = None

    def set_result_callback(self, callback):
        """Register callback for each detection result: callback(DetectionResult)."""
        self._on_result_callback = callback

    def start(self):
        """Start the inference loop."""
        if self._running:
            return

        self.detector.load_model()
        self._running = True
        self._thread = threading.Thread(target=self._inference_loop, daemon=True)
        self._thread.start()
        logger.info("Inference engine started")

    def stop(self):
        """Stop the inference loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("Inference engine stopped")

    def get_latest_result(self) -> tuple[np.ndarray | None, DetectionResult | None]:
        """Return (processed_frame, detection_result) thread-safely."""
        with self._lock:
            return self._latest_processed_frame, self._latest_result

    def get_annotated_frame(self) -> np.ndarray | None:
        """Return latest frame with detection boxes drawn."""
        with self._lock:
            return self._latest_annotated_frame

    def _inference_loop(self):
        """Main loop: grab frame → preprocess → detect → annotate at interval."""
        while self._running:
            frame = self.camera.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # Preprocess
            processed = self.preprocessor.process(frame)

            # Detect
            result = self.detector.detect(processed)

            # Annotate frame with detection boxes
            annotated = self.detector.annotate_frame(processed, result)

            with self._lock:
                self._latest_frame = frame
                self._latest_processed_frame = processed
                self._latest_result = result
                self._latest_annotated_frame = annotated

            # Notify callback
            if self._on_result_callback:
                try:
                    self._on_result_callback(result)
                except Exception as e:
                    logger.error(f"Result callback error: {e}")

            time.sleep(settings.inference_interval)
