"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.camera.capture import CameraCapture
from backend.camera.preprocessor import ImagePreprocessor
from backend.inference.detector import Detector
from backend.inference.engine import InferenceEngine
from backend.extractor.rule_engine import RuleEngine
from backend.sop.state_machine import StateMachineEngine
from backend.sop.sop_manager import SopManager
from backend.alert.manager import AlertManager
from backend.models.database import init_db, SessionLocal
from backend.models.record import OperationRecord

# Import routers
from backend.api.ws import router as ws_router, heartbeat_loop, broadcast_event
from backend.api.sop import router as sop_router
from backend.api.alert_config import router as alert_config_router
from backend.api.stats import router as stats_router
from backend.api import monitor as monitor_api
from backend.api import video as video_api
from backend.api import alert_config as alert_config_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared components (initialized in lifespan)
camera: CameraCapture | None = None
inference_engine: InferenceEngine | None = None
state_machine: StateMachineEngine | None = None
alert_manager: AlertManager | None = None
rule_engine: RuleEngine | None = None


def _load_sop_rules(sop_mgr: SopManager, rules: RuleEngine):
    """Load all SOP definitions into the rule engine."""
    for sop_meta in sop_mgr.list_sops():
        try:
            sop = sop_mgr.load(sop_meta["sop_id"])
            step_rules = [
                {
                    "step_id": step.step_id,
                    "step_name": step.name,
                    "expected_objects": step.rule.expected_objects,
                    "min_confidence": step.rule.min_confidence,
                    "required_count": step.rule.required_count,
                }
                for step in sop.steps
            ]
            rules.load_rules(sop.sop_id, step_rules)
        except Exception as e:
            logger.warning(f"Failed to load rules for {sop_meta['sop_id']}: {e}")


def _save_record(event):
    """Persist a SopEvent to the database."""
    db = SessionLocal()
    try:
        record = OperationRecord(
            sop_id=event.sop_id,
            step_id=event.step_id,
            step_name=event.step_name,
            status=event.status,
            confidence=event.confidence,
            details=event.details,
            timestamp=event.timestamp,
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save record: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global camera, inference_engine, state_machine, alert_manager, rule_engine

    logger.info("Starting AI SOP Monitor...")

    # Initialize database
    init_db()

    # Initialize components
    camera = CameraCapture()
    detector = Detector()
    inference_engine = InferenceEngine(camera, detector)
    state_machine = StateMachineEngine()
    alert_manager = AlertManager()
    rule_engine = RuleEngine()
    sop_manager = SopManager()

    # Load SOP rules into rule engine
    _load_sop_rules(sop_manager, rule_engine)

    # Wire up API modules
    monitor_api.set_state_machine(state_machine)
    monitor_api.set_alert_manager(alert_manager)
    alert_config_api.set_alert_manager(alert_manager)
    video_api.set_capture(camera)
    video_api.set_preprocessor(inference_engine.preprocessor)
    video_api.set_inference_engine(inference_engine)

    # Detection result callback: detection → rules → state machine → alert → db → ws
    def on_detection(result):
        """Process each detection through the full pipeline."""
        for sop_id in [m["sop_id"] for m in sop_manager.list_sops()]:
            events = rule_engine.evaluate(sop_id, result)
            for event in events:
                state_changed = state_machine.process_event(event)
                alert = alert_manager.process_event(event)
                # Persist to DB
                _save_record(event)
                # Broadcast via WebSocket (fire-and-forget from sync thread)
                if state_changed or alert:
                    try:
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(
                            asyncio.ensure_future,
                            broadcast_event("sop_event", event.to_dict()),
                        )
                    except RuntimeError:
                        pass  # No event loop running yet

    inference_engine.set_result_callback(on_detection)

    # Start camera
    camera_ok = camera.start()
    if camera_ok:
        inference_engine.start()
    else:
        logger.warning("Camera not available - running in API-only mode")

    # Start heartbeat background task
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    yield

    # Shutdown
    logger.info("Shutting down AI SOP Monitor...")
    heartbeat_task.cancel()
    if inference_engine:
        inference_engine.stop()
    if camera:
        camera.stop()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered SOP compliance monitoring system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ws_router)
app.include_router(sop_router)
app.include_router(monitor_api.router)
app.include_router(video_api.router)
app.include_router(alert_config_router)
app.include_router(stats_router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "camera": camera.is_running if camera else False,
        "inference": inference_engine._running if inference_engine else False,
    }
