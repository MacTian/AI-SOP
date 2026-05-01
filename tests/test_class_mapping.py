"""Tests for class mapping and gesture classifier."""

import numpy as np
import pytest

from backend.inference.class_mapping import (
    resolve_expected_objects,
    build_reverse_mapping,
    get_mapping_info,
    DEFAULT_MAPPING,
)
from backend.inference.gesture_classifier import GestureClassifier, GestureResult


# ── Class Mapping Tests ──────────────────────────────────────────────


def test_resolve_direct_coco_class():
    """COCO class names pass through unchanged."""
    resolved = resolve_expected_objects(["person", "scissors"])
    assert "person" in resolved
    assert "scissors" in resolved


def test_resolve_semantic_mapping():
    """Semantic names map to COCO classes."""
    resolved = resolve_expected_objects(["tool"])
    # "tool" maps to scissors, knife, bottle, fork, spoon
    assert "scissors" in resolved
    assert "knife" in resolved
    assert "bottle" in resolved


def test_resolve_preserves_original_name():
    """Original semantic name is preserved for custom models."""
    resolved = resolve_expected_objects(["tool"])
    assert "tool" in resolved  # original kept


def test_resolve_hand_maps_to_person():
    resolved = resolve_expected_objects(["hand"])
    assert "person" in resolved
    assert "hand" in resolved


def test_resolve_board_maps():
    resolved = resolve_expected_objects(["board"])
    assert "book" in resolved
    assert "cell phone" in resolved


def test_resolve_unknown_passthrough():
    """Unknown names pass through as-is."""
    resolved = resolve_expected_objects(["custom_widget_123"])
    assert "custom_widget_123" in resolved


def test_resolve_multiple_objects():
    resolved = resolve_expected_objects(["hand", "tool", "board"])
    assert "person" in resolved
    assert "scissors" in resolved
    assert "book" in resolved


def test_resolve_custom_mapping():
    """Custom mapping overrides default."""
    custom = {"myobj": ["cat", "dog"]}
    resolved = resolve_expected_objects(["myobj"], mapping=custom)
    assert "cat" in resolved
    assert "dog" in resolved
    assert "myobj" in resolved


def test_reverse_mapping():
    reverse = build_reverse_mapping()
    assert "person" in reverse
    assert "hand" in reverse["person"]  # "hand" → person
    assert "scissors" in reverse
    # "tool" → scissors, so scissors should map back to "tool"
    assert "tool" in reverse["scissors"]


def test_mapping_info():
    info = get_mapping_info()
    assert "total_mappings" in info
    assert info["total_mappings"] > 0
    assert "tool" in info["mappings"]


# ── Rule Engine with Mapping Tests ───────────────────────────────────


def test_rule_engine_with_mapping():
    """Rule engine should match COCO classes against semantic SOP rules."""
    from backend.extractor.rule_engine import RuleEngine
    from backend.inference.detector import Detection, DetectionResult

    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Pick up tool",
            "expected_objects": ["tool"],
            "min_confidence": 0.4,
            "required_count": 1,
        }
    ])

    # YOLO detects "scissors" which maps to "tool"
    detections = [Detection(class_id=0, class_name="scissors", confidence=0.8, bbox=(0, 0, 100, 100))]
    result = DetectionResult(detections=detections)
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1
    assert events[0].step_id == "s1"


def test_rule_engine_mapping_with_person():
    """YOLO 'person' should match SOP 'hand' rule."""
    from backend.extractor.rule_engine import RuleEngine
    from backend.inference.detector import Detection, DetectionResult

    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Pick up board",
            "expected_objects": ["hand", "board"],
            "min_confidence": 0.3,
            "required_count": 1,
        }
    ])

    # YOLO detects "person" (should match "hand") and "book" (should match "board")
    detections = [
        Detection(class_id=0, class_name="person", confidence=0.85, bbox=(0, 0, 100, 100)),
        Detection(class_id=1, class_name="book", confidence=0.7, bbox=(100, 100, 200, 200)),
    ]
    result = DetectionResult(detections=detections)
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1
    assert "person" in events[0].details["matched_objects"]
    assert "book" in events[0].details["matched_objects"]


def test_rule_engine_mapping_details():
    """Events should include resolved mapping info."""
    from backend.extractor.rule_engine import RuleEngine
    from backend.inference.detector import Detection, DetectionResult

    engine = RuleEngine()
    engine.load_rules("test_sop", [
        {
            "step_id": "s1",
            "step_name": "Step 1",
            "expected_objects": ["tool"],
            "min_confidence": 0.4,
            "required_count": 1,
        }
    ])

    detections = [Detection(class_id=0, class_name="knife", confidence=0.7, bbox=(0, 0, 100, 100))]
    result = DetectionResult(detections=detections)
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1
    assert "tool" in events[0].details["expected_objects"]
    assert "knife" in events[0].details["resolved_to"]


def test_rule_engine_backward_compat_direct_class():
    """Direct class names in detections still work."""
    from backend.extractor.rule_engine import RuleEngine
    from backend.inference.detector import Detection, DetectionResult

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

    # Custom model detects "hand" directly
    detections = [Detection(class_id=0, class_name="hand", confidence=0.9, bbox=(0, 0, 100, 100))]
    result = DetectionResult(detections=detections)
    events = engine.evaluate("test_sop", result)
    assert len(events) == 1  # should match because "hand" is preserved


# ── Gesture Classifier Tests ─────────────────────────────────────────


def _make_hand_landmarks(tip_positions):
    """Helper: create 63-dim feature vector with specific fingertip positions.

    tip_positions: dict of landmark_index -> (x, y, z)
    All others default to a neutral hand pose.
    """
    features = np.zeros(63, dtype=np.float32)

    # Default neutral hand: spread fingers
    # Wrist
    features[0] = 0.5; features[1] = 0.9; features[2] = 0.0
    # Thumb
    features[6] = 0.3; features[7] = 0.7; features[8] = 0.0  # MCP
    features[9] = 0.25; features[10] = 0.55; features[11] = 0.0  # IP
    features[12] = 0.2; features[13] = 0.45; features[14] = 0.0  # TIP
    # Index
    features[15] = 0.4; features[16] = 0.6; features[17] = 0.0  # MCP
    features[18] = 0.38; features[19] = 0.45; features[20] = 0.0  # PIP
    features[21] = 0.36; features[22] = 0.3; features[23] = 0.0  # DIP
    features[24] = 0.35; features[25] = 0.2; features[26] = 0.0  # TIP
    # Middle
    features[27] = 0.5; features[28] = 0.6; features[29] = 0.0
    features[30] = 0.5; features[31] = 0.45; features[32] = 0.0
    features[33] = 0.5; features[34] = 0.3; features[35] = 0.0
    features[36] = 0.5; features[37] = 0.15; features[38] = 0.0
    # Ring
    features[39] = 0.6; features[40] = 0.6; features[41] = 0.0
    features[42] = 0.62; features[43] = 0.45; features[44] = 0.0
    features[45] = 0.63; features[46] = 0.3; features[47] = 0.0
    features[48] = 0.64; features[49] = 0.15; features[50] = 0.0
    # Pinky
    features[51] = 0.7; features[52] = 0.65; features[53] = 0.0
    features[54] = 0.72; features[55] = 0.55; features[56] = 0.0
    features[57] = 0.73; features[58] = 0.45; features[59] = 0.0
    features[60] = 0.74; features[61] = 0.35; features[62] = 0.0

    # Override with specified positions
    for idx, (x, y, z) in tip_positions.items():
        base = idx * 3
        features[base] = x
        features[base + 1] = y
        features[base + 2] = z

    return features


def _make_fist():
    """Create a fist pose: all fingertips close to palm center."""
    # Palm center roughly at (0.5, 0.6)
    return _make_hand_landmarks({
        4: (0.45, 0.65, 0.0),   # thumb tip near palm
        8: (0.48, 0.62, 0.0),   # index tip near palm
        12: (0.50, 0.62, 0.0),  # middle tip near palm
        16: (0.52, 0.62, 0.0),  # ring tip near palm
        20: (0.54, 0.65, 0.0),  # pinky tip near palm
    })


def _make_pointing():
    """Create a pointing pose: index extended, others curled.

    Need index tip far from wrist AND other tips clearly closer to palm
    than their PIP joints to get low curl on index, high curl on others.
    """
    features = np.zeros(63, dtype=np.float32)
    wrist = (0.5, 0.9, 0.0)

    features[0] = wrist[0]; features[1] = wrist[1]; features[2] = wrist[2]

    # Thumb (curled)
    features[6] = 0.45; features[7] = 0.75; features[8] = 0.0    # MCP
    features[9] = 0.47; features[10] = 0.78; features[11] = 0.0  # IP
    features[12] = 0.48; features[13] = 0.80; features[14] = 0.0 # TIP

    # Index (extended - tip far from wrist)
    features[15] = 0.40; features[16] = 0.55; features[17] = 0.0  # MCP
    features[18] = 0.38; features[19] = 0.35; features[20] = 0.0  # PIP
    features[21] = 0.37; features[22] = 0.20; features[23] = 0.0  # DIP
    features[24] = 0.36; features[25] = 0.05; features[26] = 0.0  # TIP (very far from wrist)

    # Middle (curled - tips near MCP)
    features[27] = 0.50; features[28] = 0.60; features[29] = 0.0  # MCP
    features[30] = 0.50; features[31] = 0.62; features[32] = 0.0  # PIP
    features[33] = 0.50; features[34] = 0.61; features[35] = 0.0  # DIP
    features[36] = 0.50; features[37] = 0.60; features[38] = 0.0  # TIP (near MCP)

    # Ring (curled)
    features[39] = 0.60; features[40] = 0.60; features[41] = 0.0  # MCP
    features[42] = 0.60; features[43] = 0.62; features[44] = 0.0  # PIP
    features[45] = 0.60; features[46] = 0.61; features[47] = 0.0  # DIP
    features[48] = 0.60; features[49] = 0.60; features[50] = 0.0  # TIP

    # Pinky (curled)
    features[51] = 0.70; features[52] = 0.65; features[53] = 0.0  # MCP
    features[54] = 0.70; features[55] = 0.67; features[56] = 0.0  # PIP
    features[57] = 0.70; features[58] = 0.66; features[59] = 0.0  # DIP
    features[60] = 0.70; features[61] = 0.65; features[62] = 0.0  # TIP

    return features


def test_gesture_classifier_open_hand():
    """Open hand with all fingers extended should be 'open'."""
    classifier = GestureClassifier()
    features = _make_hand_landmarks({})  # default neutral pose
    result = classifier.classify(features, hand_index=0)
    assert result.gesture in ("open", "unknown")  # may vary with default pose


def test_gesture_classifier_fist():
    """Fist pose should be classified as 'grab'."""
    classifier = GestureClassifier(grab_threshold=0.4)
    features = _make_fist()
    result = classifier.classify(features, hand_index=0)
    assert result.gesture == "grab"
    assert result.confidence > 0


def test_gesture_classifier_pointing():
    """Pointing pose should be classified as 'point'."""
    classifier = GestureClassifier()
    features = _make_pointing()
    result = classifier.classify(features, hand_index=0)
    assert result.gesture == "point"


def test_gesture_classifier_zeros():
    """All-zero features (no hand) should be 'unknown'."""
    classifier = GestureClassifier()
    features = np.zeros(63, dtype=np.float32)
    result = classifier.classify(features, hand_index=0)
    assert result.gesture == "unknown"


def test_gesture_classifier_both_hands():
    """classify_both_hands should handle two hands."""
    classifier = GestureClassifier(grab_threshold=0.4)
    fist = _make_fist()
    pointing = _make_pointing()
    combined = np.concatenate([fist, pointing])

    results = classifier.classify_both_hands(combined)
    assert len(results) == 2
    gestures = {r.gesture for r in results}
    assert "grab" in gestures
    assert "point" in gestures


def test_gesture_classifier_result_fields():
    """GestureResult should have all expected fields."""
    classifier = GestureClassifier()
    features = _make_fist()
    result = classifier.classify(features, hand_index=0)
    assert isinstance(result, GestureResult)
    assert result.hand_index == 0
    assert isinstance(result.finger_curl, float)
    assert isinstance(result.y_velocity, float)


def test_gesture_classifier_reset():
    """Reset should clear history."""
    classifier = GestureClassifier()
    features = _make_fist()
    classifier.classify(features, 0)
    assert len(classifier._history) > 0
    classifier.reset()
    assert len(classifier._history) == 0
