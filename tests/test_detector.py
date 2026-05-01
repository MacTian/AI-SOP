"""Tests for detector module."""

import numpy as np
from backend.inference.detector import Detector, Detection, DetectionResult


def test_detector_mock_mode():
    detector = Detector()
    assert detector.is_mock is True


def test_detector_mock_detect():
    detector = Detector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)
    assert isinstance(result, DetectionResult)
    assert len(result.detections) > 0
    for det in result.detections:
        assert isinstance(det, Detection)
        assert det.confidence > 0
        assert len(det.bbox) == 4


def test_detector_annotate_frame():
    detector = Detector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)
    annotated = detector.annotate_frame(frame, result)
    assert annotated.shape == frame.shape
    # Annotated frame should differ from original (boxes drawn)
    assert not np.array_equal(annotated, frame)


def test_detection_dataclass():
    det = Detection(class_id=0, class_name="person", confidence=0.9, bbox=(10, 20, 100, 200))
    assert det.class_id == 0
    assert det.class_name == "person"
    assert det.confidence == 0.9
    assert det.bbox == (10, 20, 100, 200)


def test_detection_result_defaults():
    result = DetectionResult()
    assert result.detections == []
    assert result.frame_time == 0.0
    assert result.inference_time == 0.0


def test_detector_get_color():
    detector = Detector()
    color1 = detector._get_color(0)
    color2 = detector._get_color(1)
    assert color1 != color2
    assert len(color1) == 3
