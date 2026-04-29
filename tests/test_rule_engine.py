"""Tests for rule engine."""

from backend.extractor.rule_engine import RuleEngine
from backend.inference.detector import Detection, DetectionResult


def make_detections(classes_and_confs):
    """Helper to create DetectionResult from list of (class_name, confidence)."""
    detections = []
    for i, (cls, conf) in enumerate(classes_and_confs):
        detections.append(Detection(
            class_id=i,
            class_name=cls,
            confidence=conf,
            bbox=(0, 0, 100, 100),
        ))
    return DetectionResult(detections=detections)


def test_rule_engine_empty():
    engine = RuleEngine()
    result = make_detections([("hand", 0.9)])
    events = engine.evaluate("nonexistent", result)
    assert events == []


def test_rule_engine_basic_match():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["hand"],
            "min_confidence": 0.5,
            "required_count": 1,
        }
    ])
    result = make_detections([("hand", 0.9)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1
    assert events[0].step_id == "s1"
    assert events[0].status == "detected"
    assert events[0].confidence == 0.9


def test_rule_engine_no_match_low_confidence():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["hand"],
            "min_confidence": 0.8,
            "required_count": 1,
        }
    ])
    result = make_detections([("hand", 0.5)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 0


def test_rule_engine_wrong_class():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["tool"],
            "min_confidence": 0.5,
            "required_count": 1,
        }
    ])
    result = make_detections([("hand", 0.9)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 0


def test_rule_engine_multiple_steps():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["hand"],
            "min_confidence": 0.5,
            "required_count": 1,
        },
        {
            "step_id": "s2",
            "step_name": "Step 2",
            "expected_objects": ["tool"],
            "min_confidence": 0.5,
            "required_count": 1,
        },
    ])
    result = make_detections([("hand", 0.9), ("tool", 0.8)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 2
    step_ids = {e.step_id for e in events}
    assert step_ids == {"s1", "s2"}


def test_rule_engine_required_count():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["hand"],
            "min_confidence": 0.5,
            "required_count": 2,
        }
    ])
    # Only one hand detected
    result = make_detections([("hand", 0.9)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 0

    # Two hands detected
    result = make_detections([("hand", 0.9), ("hand", 0.8)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1


def test_rule_engine_clear_rules():
    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {"step_id": "s1", "step_name": "Step 1", "expected_objects": ["hand"]}
    ])
    engine.clear_rules("test_sop")
    result = make_detections([("hand", 0.9)])
    events = engine.evaluate("test_sop", result)
    assert len(events) == 0
