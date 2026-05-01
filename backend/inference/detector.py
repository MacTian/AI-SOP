"""YOLO object detector with real model support and mock fallback."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single object detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)


@dataclass
class DetectionResult:
    """Full frame detection results."""
    detections: list[Detection] = field(default_factory=list)
    frame_time: float = 0.0
    inference_time: float = 0.0
    annotated_frame: np.ndarray | None = None  # frame with drawn boxes


class Detector:
    """YOLO-based object detector.

    Loads a real YOLOv8 model if available, otherwise falls back to mock.
    """

    def __init__(self):
        self.confidence_threshold = settings.confidence_threshold
        self._model = None
        self._class_names: list[str] = []
        self._is_mock = True

    def load_model(self, model_path: str | None = None):
        """Load YOLO model. Falls back to mock if model file not found."""
        path = model_path or settings.model_path

        # Try loading real model
        try:
            from ultralytics import YOLO
            if Path(path).exists():
                self._model = YOLO(path)
            else:
                # Download default model if not exists
                logger.info(f"Model {path} not found, downloading yolov8n.pt...")
                self._model = YOLO("yolov8n.pt")
            self._class_names = list(self._model.names.values())
            self._is_mock = False
            logger.info(f"YOLO model loaded: {len(self._class_names)} classes")
        except ImportError:
            logger.warning("ultralytics not installed, using mock detector")
            self._init_mock()
        except Exception as e:
            logger.warning(f"Failed to load YOLO model: {e}, using mock detector")
            self._init_mock()

    def _init_mock(self):
        """Initialize mock mode."""
        self._is_mock = True
        self._class_names = [
            "person", "tool", "part", "box", "hand",
            "screwdriver", "wrench", "board", "solder", "label"
        ]

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """Run detection on a single frame."""
        start = time.time()

        if self._is_mock:
            detections = self._mock_detect(frame)
            return DetectionResult(
                detections=detections,
                frame_time=time.time(),
                inference_time=time.time() - start,
            )

        # Real YOLO inference
        results = self._model(frame, conf=self.confidence_threshold, verbose=False)
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                box = boxes[i]
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self._class_names[cls_id] if cls_id < len(self._class_names) else str(cls_id)
                detections.append(Detection(
                    class_id=cls_id,
                    class_name=cls_name,
                    confidence=round(conf, 3),
                    bbox=(x1, y1, x2, y2),
                ))

        return DetectionResult(
            detections=detections,
            frame_time=time.time(),
            inference_time=time.time() - start,
        )

    def annotate_frame(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
        """Draw detection boxes on frame."""
        annotated = frame.copy()

        for det in result.detections:
            x1, y1, x2, y2 = det.bbox
            # Color by class
            color = self._get_color(det.class_id)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Label
            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return annotated

    def _get_color(self, class_id: int) -> tuple[int, int, int]:
        """Get a consistent color for a class ID."""
        colors = [
            (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
            (0, 255, 255), (255, 0, 255), (128, 255, 0), (255, 128, 0),
            (0, 128, 255), (128, 0, 255),
        ]
        return colors[class_id % len(colors)]

    def _mock_detect(self, frame: np.ndarray) -> list[Detection]:
        """Generate mock detections for testing."""
        h, w = frame.shape[:2]
        return [
            Detection(
                class_id=0, class_name="person", confidence=0.87,
                bbox=(int(w * 0.2), int(h * 0.1), int(w * 0.6), int(h * 0.9)),
            ),
            Detection(
                class_id=1, class_name="tool", confidence=0.72,
                bbox=(int(w * 0.6), int(h * 0.3), int(w * 0.8), int(h * 0.5)),
            ),
        ]
