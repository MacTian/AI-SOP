"""Tests for training session and step analyzer."""

import time
import pytest
import numpy as np

from backend.training.session import TrainingSession, FrameRecord, TrainingState
from backend.training.analyzer import StepAnalyzer
from backend.inference.detector import DetectionResult, Detection


def _make_detection(class_name: str, confidence: float = 0.8) -> Detection:
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        bbox=[10, 10, 100, 100],
    )


def _make_result(class_names: list[str]) -> DetectionResult:
    return DetectionResult(
        detections=[_make_detection(n) for n in class_names],
        inference_time=0.01,
    )


# --- TrainingSession tests ---

def test_session_initial_state():
    session = TrainingSession()
    assert session.state.status == "idle"
    assert not session.is_recording
    assert session.frame_count == 0


def test_session_start():
    session = TrainingSession()
    ok = session.start(sop_name="Test SOP", sop_description="desc")
    assert ok is True
    assert session.is_recording
    assert session.state.status == "recording"


def test_session_start_twice():
    session = TrainingSession()
    session.start(sop_name="Test")
    ok = session.start(sop_name="Test 2")
    assert ok is False  # already recording


def test_session_record_frame():
    session = TrainingSession()
    session.start()
    result = _make_result(["person", "box"])
    session.record_frame(result)
    assert session.frame_count == 1
    session.record_frame(_make_result(["person"]))
    assert session.frame_count == 2


def test_session_record_when_not_recording():
    session = TrainingSession()
    session.record_frame(_make_result(["person"]))  # should be no-op
    assert session.frame_count == 0


def test_session_stop():
    session = TrainingSession()
    session.start()
    session.record_frame(_make_result(["person"]))
    ok = session.stop()
    assert ok is True
    assert session.state.status == "analyzing"
    assert session.state.frame_count == 1
    assert session.state.duration >= 0


def test_session_stop_when_not_recording():
    session = TrainingSession()
    ok = session.stop()
    assert ok is False


def test_session_get_frames():
    session = TrainingSession()
    session.start()
    session.record_frame(_make_result(["person"]))
    session.record_frame(_make_result(["box"]))
    frames = session.get_frames()
    assert len(frames) == 2
    assert frames[0].detections[0]["class_name"] == "person"
    assert frames[1].detections[0]["class_name"] == "box"


def test_session_get_state_dict():
    session = TrainingSession()
    session.start(sop_name="Test", sop_description="desc")
    d = session.get_state_dict()
    assert d["status"] == "recording"
    assert d["sop_name"] == "Test"
    assert d["sop_description"] == "desc"


def test_session_reset():
    session = TrainingSession()
    session.start()
    session.record_frame(_make_result(["person"]))
    session.stop()
    session.reset()
    assert session.state.status == "idle"
    assert session.frame_count == 0


# --- StepAnalyzer tests ---

def test_analyzer_too_few_frames():
    analyzer = StepAnalyzer(min_step_frames=5)
    frames = [
        FrameRecord(timestamp=time.time(), detections=[{"class_name": "person", "confidence": 0.8}])
        for _ in range(3)
    ]
    steps = analyzer.analyze(frames)
    assert steps == []


def test_analyzer_single_step():
    """Many frames with same objects → one step."""
    analyzer = StepAnalyzer(min_step_frames=3, min_step_duration=0.1)
    t0 = time.time()
    frames = [
        FrameRecord(
            timestamp=t0 + i * 0.1,
            detections=[{"class_name": "person", "confidence": 0.8}],
        )
        for i in range(10)
    ]
    steps = analyzer.analyze(frames)
    assert len(steps) >= 1
    assert "person" in steps[0]["expected_objects"]


def test_analyzer_detects_change():
    """Frames change from person+box to person+scissors → two steps."""
    analyzer = StepAnalyzer(
        min_step_frames=3,
        min_step_duration=0.1,
        change_threshold=0.3,
    )
    t0 = time.time()
    frames = []
    # Phase 1: person + box
    for i in range(8):
        frames.append(FrameRecord(
            timestamp=t0 + i * 0.1,
            detections=[
                {"class_name": "person", "confidence": 0.8},
                {"class_name": "box", "confidence": 0.7},
            ],
        ))
    # Phase 2: person + scissors
    for i in range(8):
        frames.append(FrameRecord(
            timestamp=t0 + 0.8 + i * 0.1,
            detections=[
                {"class_name": "person", "confidence": 0.8},
                {"class_name": "scissors", "confidence": 0.75},
            ],
        ))
    steps = analyzer.analyze(frames)
    assert len(steps) >= 2
    # First step should have box
    assert "box" in steps[0]["expected_objects"]
    # Second step should have scissors
    assert "scissors" in steps[-1]["expected_objects"]


def test_analyzer_merge_similar_steps():
    """Consecutive segments with same objects get merged."""
    analyzer = StepAnalyzer(
        min_step_frames=3,
        min_step_duration=0.1,
        change_threshold=0.9,  # high threshold → fewer change points → more merging
    )
    t0 = time.time()
    frames = [
        FrameRecord(
            timestamp=t0 + i * 0.1,
            detections=[{"class_name": "person", "confidence": 0.8}],
        )
        for i in range(20)
    ]
    steps = analyzer.analyze(frames)
    # All same objects → should be merged into 1 step
    assert len(steps) == 1


def test_analyzer_step_metadata():
    """Verify step dict contains expected fields."""
    analyzer = StepAnalyzer(min_step_frames=3, min_step_duration=0.1)
    t0 = time.time()
    frames = [
        FrameRecord(
            timestamp=t0 + i * 0.1,
            detections=[{"class_name": "person", "confidence": 0.85}],
        )
        for i in range(10)
    ]
    steps = analyzer.analyze(frames)
    assert len(steps) >= 1
    step = steps[0]
    assert "step_id" in step
    assert "name" in step
    assert "expected_objects" in step
    assert "min_confidence" in step
    assert "timeout" in step
    assert "estimated_duration" in step
    assert step["step_id"].startswith("auto_step_")


def test_analyzer_step_name_generation():
    """Step name should reflect detected objects."""
    analyzer = StepAnalyzer(min_step_frames=3, min_step_duration=0.1)
    t0 = time.time()
    # Scissors → "剪切"
    frames = [
        FrameRecord(
            timestamp=t0 + i * 0.1,
            detections=[
                {"class_name": "person", "confidence": 0.8},
                {"class_name": "scissors", "confidence": 0.75},
            ],
        )
        for i in range(10)
    ]
    steps = analyzer.analyze(frames)
    assert len(steps) >= 1
    assert "剪切" in steps[0]["name"]


def test_frame_record_dataclass():
    fr = FrameRecord(
        timestamp=1.0,
        detections=[{"class_name": "person", "confidence": 0.9}],
    )
    assert fr.timestamp == 1.0
    assert len(fr.detections) == 1
    assert fr.frame_thumbnail is None
