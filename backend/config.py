"""Application configuration using Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


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
    model_path: str = "models/yolov8n.pt"
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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_prefix = "SOP_"


settings = Settings()
