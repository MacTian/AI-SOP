"""SQLite database initialization and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite specific
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined via Base metadata."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Apply simple column additions for schema evolution."""
    import logging
    logger = logging.getLogger(__name__)

    with engine.connect() as conn:
        # Check if screenshot_path column exists in operation_records
        try:
            result = conn.execute(text("PRAGMA table_info(operation_records)"))
            columns = {row[1] for row in result}
            if "screenshot_path" not in columns:
                conn.execute(text("ALTER TABLE operation_records ADD COLUMN screenshot_path VARCHAR"))
                conn.commit()
                logger.info("Migration: added screenshot_path column to operation_records")
        except Exception as e:
            logger.debug(f"Migration check skipped: {e}")
