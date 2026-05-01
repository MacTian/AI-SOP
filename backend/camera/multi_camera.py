"""Multi-camera manager: runs independent capture + inference threads per camera."""

import threading
import logging
from typing import Callable

from backend.config import settings
from backend.camera.capture import CameraCapture
from backend.inference.detector import Detector
from backend.inference.engine import InferenceEngine

logger = logging.getLogger(__name__)


class MultiCameraManager:
    """Manages multiple cameras, each with its own capture and inference engine.

    Each camera runs an independent pipeline: capture → preprocess → detect → callback.
    The callback receives (camera_id, DetectionResult).
    """

    def __init__(self):
        self._cameras: dict[int, CameraCapture] = {}
        self._engines: dict[int, InferenceEngine] = {}
        self._callback: Callable[[int, object], None] | None = None

    def set_callback(self, callback: Callable[[int, object], None]):
        """Set callback receiving (camera_id, DetectionResult) for each detection."""
        self._callback = callback

    def _parse_device_ids(self) -> list[int]:
        """Parse camera device IDs from config."""
        if settings.camera_devices:
            return [int(d.strip()) for d in settings.camera_devices.split(",") if d.strip()]
        return [settings.camera_device]

    def start(self) -> dict[int, bool]:
        """Start all configured cameras. Returns {device_id: success}."""
        device_ids = self._parse_device_ids()
        results = {}

        detector = Detector()

        for device_id in device_ids:
            camera = CameraCapture(device=device_id)
            engine = InferenceEngine(camera, detector)

            # Wire up callback with camera_id closure
            cam_id = device_id
            engine.set_result_callback(
                lambda result, cid=cam_id: self._on_result(cid, result)
            )

            camera_ok = camera.start()
            if camera_ok:
                engine.start()
                self._cameras[device_id] = camera
                self._engines[device_id] = engine
                results[device_id] = True
                logger.info(f"Camera {device_id} started successfully")
            else:
                results[device_id] = False
                logger.warning(f"Camera {device_id} failed to start")

        return results

    def stop(self):
        """Stop all cameras and engines."""
        for device_id, engine in self._engines.items():
            engine.stop()
        for device_id, camera in self._cameras.items():
            camera.stop()
        self._engines.clear()
        self._cameras.clear()
        logger.info("All cameras stopped")

    def get_camera(self, device_id: int) -> CameraCapture | None:
        """Get camera instance by device ID."""
        return self._cameras.get(device_id)

    def get_engine(self, device_id: int) -> InferenceEngine | None:
        """Get inference engine by device ID."""
        return self._engines.get(device_id)

    def get_active_cameras(self) -> list[int]:
        """Return list of active camera device IDs."""
        return list(self._cameras.keys())

    def get_frame(self, device_id: int):
        """Get latest annotated frame from a specific camera."""
        engine = self._engines.get(device_id)
        if engine:
            return engine.get_annotated_frame()
        return None

    def _on_result(self, camera_id: int, result):
        """Forward detection results with camera ID."""
        if self._callback:
            try:
                self._callback(camera_id, result)
            except Exception as e:
                logger.error(f"Multi-camera callback error for camera {camera_id}: {e}")
