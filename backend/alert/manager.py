"""Alert manager: handles alert generation, escalation, deduplication."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.config import settings
from backend.extractor.event import SopEvent

logger = logging.getLogger(__name__)

# Alert level escalation order
LEVEL_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}


@dataclass
class AlertRule:
    """Configurable alert rule."""
    sop_id: str
    step_id: str
    level: str = "warning"
    escalation_count: int = 3  # escalate after N repeats
    cooldown: int = 0  # override global cooldown (0 = use global)


@dataclass
class Alert:
    """An alert instance."""
    alert_id: str
    level: str  # info, warning, error, critical
    sop_id: str
    step_id: str
    step_name: str
    message: str
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    repeat_count: int = 1


class AlertManager:
    """Manages alerts with deduplication, escalation, and configurable rules."""

    def __init__(self, cooldown: int | None = None):
        self._cooldown = cooldown or settings.alert_cooldown
        self._alerts: list[Alert] = []
        self._last_alert_time: dict[str, float] = {}
        self._repeat_counts: dict[str, int] = {}  # key -> count
        self._rules: dict[str, AlertRule] = {}  # "sop_id:step_id" -> rule
        self._on_alert_callback = None
        self._counter = 0

    def set_callback(self, callback):
        """Register callback for new alerts: callback(Alert)."""
        self._on_alert_callback = callback

    def add_rule(self, rule: AlertRule):
        """Add or update an alert rule."""
        key = f"{rule.sop_id}:{rule.step_id}"
        self._rules[key] = rule
        logger.info(f"Alert rule set: {key} -> {rule.level}")

    def remove_rule(self, sop_id: str, step_id: str):
        """Remove an alert rule."""
        self._rules.pop(f"{sop_id}:{step_id}", None)

    def get_rules(self) -> list[dict]:
        """Return all configured rules."""
        return [
            {
                "sop_id": r.sop_id,
                "step_id": r.step_id,
                "level": r.level,
                "escalation_count": r.escalation_count,
                "cooldown": r.cooldown,
            }
            for r in self._rules.values()
        ]

    def process_event(self, event: SopEvent) -> Alert | None:
        """Evaluate an event and generate an alert if needed."""
        level = self._determine_level(event)
        if level is None:
            return None

        # Check for configured rule override
        rule_key = f"{event.sop_id}:{event.step_id}"
        rule = self._rules.get(rule_key)
        if rule:
            level = rule.level

        # Deduplication with escalation
        key = f"{event.sop_id}:{event.step_id}"
        now = time.time()
        effective_cooldown = rule.cooldown if rule and rule.cooldown > 0 else self._cooldown
        last = self._last_alert_time.get(key, 0)

        if now - last < effective_cooldown:
            # Track repeat count for escalation
            self._repeat_counts[key] = self._repeat_counts.get(key, 0) + 1
            esc_count = rule.escalation_count if rule else 3
            if self._repeat_counts[key] >= esc_count:
                level = self._escalate_level(level)
                self._repeat_counts[key] = 0
            else:
                return None  # Still in cooldown, no alert yet
        else:
            self._repeat_counts[key] = 1

        # Create alert
        self._counter += 1
        alert = Alert(
            alert_id=f"alert-{self._counter}",
            level=level,
            sop_id=event.sop_id,
            step_id=event.step_id,
            step_name=event.step_name,
            message=self._format_message(event, level),
            details=event.details,
            repeat_count=self._repeat_counts.get(key, 1),
        )

        self._alerts.append(alert)
        self._last_alert_time[key] = now
        logger.warning(f"Alert [{level}]: {alert.message}")

        if self._on_alert_callback:
            try:
                self._on_alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        return alert

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        """Return recent alerts as dicts."""
        return [
            {
                "alert_id": a.alert_id,
                "level": a.level,
                "sop_id": a.sop_id,
                "step_id": a.step_id,
                "step_name": a.step_name,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged,
                "repeat_count": a.repeat_count,
            }
            for a in self._alerts[-limit:]
        ]

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert by ID."""
        for a in self._alerts:
            if a.alert_id == alert_id:
                a.acknowledged = True
                return True
        return False

    def acknowledge_all(self) -> int:
        """Acknowledge all unacknowledged alerts. Returns count."""
        count = 0
        for a in self._alerts:
            if not a.acknowledged:
                a.acknowledged = True
                count += 1
        return count

    def _determine_level(self, event: SopEvent) -> str | None:
        """Determine alert level from event. Returns None if no alert needed."""
        if event.status == "error":
            return "error"
        if event.status == "timeout":
            return "warning"
        if event.status == "skipped":
            return "info"
        return None

    def _escalate_level(self, current: str) -> str:
        """Escalate alert level by one step."""
        order = LEVEL_ORDER.get(current, 0)
        for level, lvl_order in LEVEL_ORDER.items():
            if lvl_order == order + 1:
                return level
        return "critical"  # Already at max

    def _format_message(self, event: SopEvent, level: str) -> str:
        return f"[{level.upper()}] SOP '{event.sop_id}' step '{event.step_name}': {event.status}"
