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
    # Import all models so they register with Base
    from backend.models import user  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_admin()


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


def _seed_admin():
    """Create default admin user if no users exist."""
    import logging
    import bcrypt

    logger = logging.getLogger(__name__)

    from backend.models.user import User

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            hashed = bcrypt.hashpw(
                settings.default_admin_password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")
            admin = User(
                username="admin",
                hashed_password=hashed,
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("Seeded default admin user (admin / admin123)")
    except Exception as e:
        db.rollback()
        logger.debug(f"Admin seed skipped: {e}")
    finally:
        db.close()
