"""User ORM model for authentication."""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone

from backend.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="operator")  # "admin" or "operator"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
