"""Operation record ORM model."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON

from backend.models.database import Base


class OperationRecord(Base):
    """Stores detected SOP operation events."""
    __tablename__ = "operation_records"

    id = Column(Integer, primary_key=True, index=True)
    sop_id = Column(String, index=True, nullable=False)
    step_id = Column(String, nullable=False)
    step_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # detected, completed, skipped, error
    confidence = Column(Float, default=0.0)
    details = Column(JSON, default=dict)
    screenshot_path = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
