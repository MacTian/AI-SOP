"""Rule engine: maps detection results to SOP step events."""

import logging
from backend.inference.detector import DetectionResult
from backend.inference.class_mapping import resolve_expected_objects
from backend.inference.gesture_classifier import GestureResult
from backend.extractor.event import SopEvent

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluates detection results against SOP step rules.

    Each SOP step defines detection rules (expected objects, gestures).
    The rule engine matches detections to rules and emits SopEvents.

    Supports class name mapping: SOP rules can use semantic names like
    "tool" or "board" which are automatically mapped to COCO classes.
    Also supports gesture matching (grab, point, pick_up, put_down).
    """

    def __init__(self, class_mapping: dict[str, list[str]] | None = None):
        # Map of sop_id -> list of step rules
        self._rules: dict[str, list[dict]] = {}
        self._class_mapping = class_mapping

    def load_rules(self, sop_id: str, steps: list[dict]):
        """Load step rules for an SOP definition.

        Each step dict should have:
            - step_id: str
            - step_name: str
            - expected_objects: list[str]  (class names to detect)
            - expected_gestures: list[str]  (gesture names to match)
            - min_confidence: float
            - required_count: int  (how many objects must be present)
        """
        self._rules[sop_id] = steps
        logger.info(f"Loaded {len(steps)} rules for SOP {sop_id}")

    def clear_rules(self, sop_id: str):
        """Remove rules for an SOP."""
        self._rules.pop(sop_id, None)

    def evaluate(
        self,
        sop_id: str,
        detection_result: DetectionResult,
        gesture_results: list[GestureResult] | None = None,
    ) -> list[SopEvent]:
        """Evaluate detections against rules for the given SOP.

        Args:
            sop_id: SOP identifier
            detection_result: YOLO detection results
            gesture_results: Optional gesture classification results

        Returns list of SopEvents for steps that matched.
        """
        steps = self._rules.get(sop_id, [])
        if not steps:
            return []

        events = []
        gesture_results = gesture_results or []

        for step in steps:
            expected_raw = step.get("expected_objects", [])
            expected_gestures = step.get("expected_gestures", [])
            min_conf = step.get("min_confidence", 0.5)
            required_count = step.get("required_count", 1)

            # Resolve semantic names to COCO classes
            expected_coco = resolve_expected_objects(expected_raw, self._class_mapping)

            # Count matching detections above confidence threshold
            matching = [
                d for d in detection_result.detections
                if d.class_name in expected_coco and d.confidence >= min_conf
            ]

            # Check gesture matches
            gesture_matches = []
            if expected_gestures:
                gesture_matches = [
                    g for g in gesture_results
                    if g.gesture in expected_gestures and g.confidence >= min_conf
                ]

            # Determine if rule is satisfied:
            # - If both objects and gestures required: both must match
            # - If only objects: object count >= required_count
            # - If only gestures: any gesture match
            has_object_match = len(matching) >= required_count
            has_gesture_match = len(gesture_matches) > 0

            if expected_gestures and expected_raw:
                # Both object and gesture required
                satisfied = has_object_match and has_gesture_match
            elif expected_gestures:
                # Only gesture required
                satisfied = has_gesture_match
            else:
                # Only objects required
                satisfied = has_object_match

            if satisfied:
                obj_conf = sum(d.confidence for d in matching) / len(matching) if matching else 0
                ges_conf = sum(g.confidence for g in gesture_matches) / len(gesture_matches) if gesture_matches else 0
                avg_conf = max(obj_conf, ges_conf) if gesture_matches else obj_conf

                events.append(SopEvent(
                    sop_id=sop_id,
                    step_id=step["step_id"],
                    step_name=step["step_name"],
                    status="detected",
                    confidence=round(avg_conf, 3),
                    details={
                        "matched_objects": [d.class_name for d in matching],
                        "matched_gestures": [g.gesture for g in gesture_matches],
                        "expected_objects": expected_raw,
                        "expected_gestures": expected_gestures,
                        "resolved_to": list(expected_coco),
                    },
                ))

        return events
