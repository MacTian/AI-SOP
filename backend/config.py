"""Application configuration using Pydantic Settings."""

import logging
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Global application settings, loaded from env vars or .env file."""

    app_name: str = "AI SOP Monitor"
    debug: bool = True

    # Camera
    camera_device: int = 0
    camera_devices: str = ""  # comma-separated device IDs for multi-camera, e.g. "0,1,2"
    camera_fps: int = 15
    camera_width: int = 640
    camera_height: int = 480

    # Inference
    model_path: str = str(Path(__file__).parent.parent / "models" / "yolo26n.pt")
    confidence_threshold: float = 0.5
    inference_interval: float = 0.5  # seconds between inferences

    # SOP definitions directory
    sop_dir: str = str(Path(__file__).parent.parent / "sop_definitions")

    # Database
    database_url: str = "sqlite:///./sop_monitor.db"

    # Alert
    alert_cooldown: int = 30  # seconds between duplicate alerts

    # State machine
    default_confirm_frames: int = 3  # consecutive hits needed to confirm step
    strict_order: bool = False  # reject events for non-current steps

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8000", "http://127.0.0.1:8000",
    ]

    # Auth
    secret_key: str = "sop-monitor-secret-key-change-in-production"
    token_expire_minutes: int = 480  # 8 hours
    default_admin_password: str = "admin123"

    class Config:
        env_file = ".env"
        env_prefix = "SOP_"


settings = Settings()

# Auto-generate secret key if default is still in use and no env var was set
_DEFAULT_SECRET = "sop-monitor-secret-key-change-in-production"
if settings.secret_key == _DEFAULT_SECRET and "SOP_SECRET_KEY" not in os.environ:
    settings.secret_key = secrets.token_hex(32)
    logger.warning(
        "JWT secret_key auto-generated for this session. "
        "Set SOP_SECRET_KEY env var for persistent deployments."
    )
