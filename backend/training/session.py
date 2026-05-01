"""Training session: records frames and detections during training."""

import logging
import time
import threading
from dataclasses import dataclass, field

import numpy as np

from backend.inference.detector import DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    """A single frame recorded during training."""
    timestamp: float
    detections: list[dict]  # serialized Detection objects
    frame_thumbnail: np.ndarray | None = None  # small thumbnail for reference


@dataclass
class TrainingState:
    """Current training session state."""
    status: str = "idle"  # idle, recording, analyzing, ready
    started_at: float = 0.0
    stopped_at: float = 0.0
    frame_count: int = 0
    duration: float = 0.0


class TrainingSession:
    """Manages a training recording session.

    During recording, captures detection results at each inference cycle.
    After stopping, provides data for the analyzer to identify steps.
    """

    def __init__(self):
        self._state = TrainingState()
        self._frames: list[FrameRecord] = []
        self._lock = threading.Lock()
        self._sop_name: str = ""
        self._sop_description: str = ""

    @property
    def state(self) -> TrainingState:
        return self._state

    @property
    def is_recording(self) -> bool:
        return self._state.status == "recording"

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def start(self, sop_name: str = "New SOP", sop_description: str = ""):
        """Start a new training session."""
        with self._lock:
            if self._state.status == "recording":
                logger.warning("Training already in progress")
                return False

            self._frames = []
            self._sop_name = sop_name
            self._sop_description = sop_description
            self._state = TrainingState(
                status="recording",
                started_at=time.time(),
            )
            logger.info(f"Training started: {sop_name}")
            return True

    def stop(self):
        """Stop recording."""
        with self._lock:
            if self._state.status != "recording":
                return False
            self._state.status = "analyzing"
            self._state.stopped_at = time.time()
            self._state.duration = self._state.stopped_at - self._state.started_at
            self._state.frame_count = len(self._frames)
            logger.info(f"Training stopped: {self._state.frame_count} frames recorded")
            return True

    def record_frame(self, result: DetectionResult, thumbnail: np.ndarray | None = None):
        """Record a detection result during training."""
        if not self.is_recording:
            return

        detections = [
            {
                "class_id": d.class_id,
                "class_name": d.class_name,
                "confidence": d.confidence,
                "bbox": d.bbox,
            }
            for d in result.detections
        ]

        frame = FrameRecord(
            timestamp=time.time(),
            detections=detections,
            frame_thumbnail=thumbnail,
        )

        with self._lock:
            self._frames.append(frame)
            self._state.frame_count = len(self._frames)

    def get_frames(self) -> list[FrameRecord]:
        """Get all recorded frames (for analyzer)."""
        with self._lock:
            return list(self._frames)

    def get_state_dict(self) -> dict:
        """Return serializable state."""
        return {
            "status": self._state.status,
            "sop_name": self._sop_name,
            "sop_description": self._sop_description,
            "started_at": self._state.started_at,
            "stopped_at": self._state.stopped_at,
            "frame_count": self._state.frame_count,
            "duration": round(self._state.duration, 1),
        }

    def reset(self):
        """Reset session for a new training."""
        with self._lock:
            self._frames = []
            self._state = TrainingState()
            logger.info("Training session reset")
