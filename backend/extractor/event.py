"""Event data classes for SOP operation detection."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SopEvent:
    """Represents a detected SOP operation event."""
    sop_id: str
    step_id: str
    step_name: str
    status: str  # detected, completed, skipped, error, timeout
    confidence: float = 0.0
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "sop_id": self.sop_id,
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status,
            "confidence": self.confidence,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }
