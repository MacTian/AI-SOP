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
from backend.training.session import TrainingSession
from backend.training.analyzer import StepAnalyzer
from backend.inference.lstm_trainer import LstmTrainer
from backend.models.database import init_db, SessionLocal
from backend.models.record import OperationRecord

# Import routers
from backend.api.ws import router as ws_router, heartbeat_loop, broadcast_event
from backend.api.sop import router as sop_router
from backend.api.alert_config import router as alert_config_router
from backend.api.stats import router as stats_router
from backend.api.training import router as training_router
from backend.api import monitor as monitor_api
from backend.api import video as video_api
from backend.api import alert_config as alert_config_api
from backend.api import training as training_api
from backend.api.video_analysis import router as video_analysis_router
from backend.api import video_analysis as video_analysis_api

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


def _save_record(event, screenshot_path=None):
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
            screenshot_path=screenshot_path,
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
    training_session = TrainingSession()
    step_analyzer = StepAnalyzer()
    lstm_trainer = LstmTrainer()

    # Load SOP rules into rule engine
    _load_sop_rules(sop_manager, rule_engine)

    # Wire up API modules
    monitor_api.set_state_machine(state_machine)
    monitor_api.set_alert_manager(alert_manager)
    alert_config_api.set_alert_manager(alert_manager)
    video_api.set_capture(camera)
    video_api.set_preprocessor(inference_engine.preprocessor)
    video_api.set_inference_engine(inference_engine)
    training_api.set_session(training_session)
    training_api.set_analyzer(step_analyzer)
    training_api.set_sop_manager(sop_manager)
    training_api.set_lstm_trainer(lstm_trainer)

    # Wire up video analysis API
    video_analysis_api.set_detector(detector)
    video_analysis_api.set_preprocessor(inference_engine.preprocessor)
    video_analysis_api.set_rule_engine(rule_engine)
    video_analysis_api.set_sop_manager(sop_manager)

    # Wire up monitor API for candidate tracking
    monitor_api.set_inference_engine(inference_engine)
    monitor_api.set_rule_engine(rule_engine)
    monitor_api.set_sop_manager(sop_manager)

    # Cache SOP definitions to avoid reading YAML on every frame
    _sop_cache: dict[str, object] = {}

    def _reload_sop_cache():
        _sop_cache.clear()
        for meta in sop_manager.list_sops():
            try:
                sop = sop_manager.load(meta["sop_id"])
                _sop_cache[meta["sop_id"]] = sop
            except Exception as e:
                logger.warning(f"Failed to cache SOP {meta['sop_id']}: {e}")

    _reload_sop_cache()

    # Detection result callback: detection → rules → state machine → alert → db → ws
    def on_detection(result):
        """Process each detection through the full pipeline."""
        # Record frame if training
        if training_session.is_recording:
            training_session.record_frame(result)

        # Compute candidates + run rule engine in one pass
        all_candidates = []
        sop_ids = list(_sop_cache.keys())

        for sop_id in sop_ids:
            # Rule engine evaluation
            events = rule_engine.evaluate(sop_id, result)

            # Candidate scoring
            sop = _sop_cache.get(sop_id)
            if sop:
                for step in sop.steps:
                    expected = set(step.rule.expected_objects)
                    matching = [
                        d for d in result.detections
                        if d.class_name in expected and d.confidence >= step.rule.min_confidence
                    ]
                    if matching:
                        avg_conf = sum(d.confidence for d in matching) / len(matching)
                        match_ratio = len(matching) / max(len(expected), 1)
                        all_candidates.append({
                            "sop_id": sop_id,
                            "step_id": step.step_id,
                            "step_name": step.name,
                            "confidence": round(avg_conf, 3),
                            "match_ratio": round(match_ratio, 3),
                            "score": round(avg_conf * match_ratio, 3),
                            "matched_objects": [d.class_name for d in matching],
                        })

            for event in events:
                state_changed = state_machine.process_event(event)
                alert = alert_manager.process_event(event)

                # Save screenshot for important state changes
                screenshot_path = None
                if state_changed and event.status == "detected":
                    instance = state_machine.get_instance(event.sop_id)
                    if instance:
                        step_status = instance.step_statuses.get(event.step_id)
                        if step_status and step_status.value == "completed":
                            from backend.api.video import save_screenshot
                            screenshot_path = save_screenshot(
                                event.sop_id, event.step_id, "completed"
                            )

                # Persist to DB
                _save_record(event, screenshot_path)

                # Broadcast via WebSocket (fire-and-forget from sync thread)
                try:
                    loop = asyncio.get_event_loop()
                    if state_changed:
                        loop.call_soon_threadsafe(
                            asyncio.ensure_future,
                            broadcast_event("sop_event", event.to_dict()),
                        )
                    if alert:
                        loop.call_soon_threadsafe(
                            asyncio.ensure_future,
                            broadcast_event("alert", {
                                "alert_id": alert.alert_id,
                                "level": alert.level,
                                "sop_id": alert.sop_id,
                                "step_id": alert.step_id,
                                "step_name": alert.step_name,
                                "message": alert.message,
                                "timestamp": alert.timestamp.isoformat(),
                            }),
                        )
                except RuntimeError:
                    pass  # No event loop running yet

        # Update top-3 candidates
        all_candidates.sort(key=lambda c: c["score"], reverse=True)
        monitor_api.update_candidates(all_candidates[:3])

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
app.include_router(video_analysis_router)
app.include_router(alert_config_router)
app.include_router(stats_router)
app.include_router(training_router)


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
