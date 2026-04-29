"""Rule engine: maps detection results to SOP step events."""

import logging
from backend.inference.detector import DetectionResult
from backend.extractor.event import SopEvent

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluates detection results against SOP step rules.

    Each SOP step defines detection rules (expected objects, actions).
    The rule engine matches detections to rules and emits SopEvents.
    """

    def __init__(self):
        # Map of sop_id -> list of step rules
        self._rules: dict[str, list[dict]] = {}

    def load_rules(self, sop_id: str, steps: list[dict]):
        """Load step rules for an SOP definition.

        Each step dict should have:
            - step_id: str
            - step_name: str
            - expected_objects: list[str]  (class names to detect)
            - min_confidence: float
            - required_count: int  (how many objects must be present)
        """
        self._rules[sop_id] = steps
        logger.info(f"Loaded {len(steps)} rules for SOP {sop_id}")

    def clear_rules(self, sop_id: str):
        """Remove rules for an SOP."""
        self._rules.pop(sop_id, None)

    def evaluate(self, sop_id: str, detection_result: DetectionResult) -> list[SopEvent]:
        """Evaluate detections against rules for the given SOP.

        Returns list of SopEvents for steps that matched.
        """
        steps = self._rules.get(sop_id, [])
        if not steps:
            return []

        detected_classes = {d.class_name for d in detection_result.detections}
        events = []

        for step in steps:
            expected = set(step.get("expected_objects", []))
            min_conf = step.get("min_confidence", 0.5)
            required_count = step.get("required_count", 1)

            # Count matching detections above confidence threshold
            matching = [
                d for d in detection_result.detections
                if d.class_name in expected and d.confidence >= min_conf
            ]

            if len(matching) >= required_count:
                avg_conf = sum(d.confidence for d in matching) / len(matching)
                events.append(SopEvent(
                    sop_id=sop_id,
                    step_id=step["step_id"],
                    step_name=step["step_name"],
                    status="detected",
                    confidence=round(avg_conf, 3),
                    details={"matched_objects": [d.class_name for d in matching]},
                ))

        return events
