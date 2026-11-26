"""Monitoring data API endpoints."""

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.record import OperationRecord
from backend.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor", tags=["Monitor"], dependencies=[Depends(get_current_user)])

# These will be set by main.py after engine initialization
_state_machine = None
_alert_manager = None
_inference_engine = None
_rule_engine = None
_sop_manager = None

# Cache latest detection candidates
_latest_candidates: list[dict] = []


def set_state_machine(sm):
    global _state_machine
    _state_machine = sm


def set_alert_manager(am):
    global _alert_manager
    _alert_manager = am


def set_inference_engine(engine):
    global _inference_engine
    _inference_engine = engine


def set_rule_engine(re):
    global _rule_engine
    _rule_engine = re


def set_sop_manager(sm):
    global _sop_manager
    _sop_manager = sm


def update_candidates(candidates: list[dict]):
    """Called from the detection pipeline to update latest candidates."""
    global _latest_candidates
    _latest_candidates = candidates


@router.get("/status")
async def get_status():
    """Get current monitoring status of all active SOPs."""
    if _state_machine is None:
        return {"active_sops": [], "message": "Monitor not initialized"}
    return {"active_sops": _state_machine.get_all_states()}


@router.post("/start/{sop_id}")
async def start_sop(sop_id: str):
    """Start a monitoring instance for an SOP definition.

    This is what brings a SOP to life: only a started instance tracks step
    progress, produces timeout events and screenshots, and shows up in
    `/api/monitor/status`.
    """
    if _state_machine is None or _sop_manager is None:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    if _state_machine.get_instance(sop_id) is not None:
        raise HTTPException(
            status_code=409, detail=f"SOP '{sop_id}' is already running"
        )

    try:
        definition = _sop_manager.load(sop_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not definition.steps:
        raise HTTPException(
            status_code=400, detail=f"SOP '{sop_id}' has no steps to monitor"
        )

    instance = _state_machine.start_sop(definition)
    state = instance.get_state_dict()
    await _broadcast_state(sop_id, state)
    return {"status": "started", **state}


@router.post("/stop/{sop_id}")
async def stop_sop(sop_id: str):
    """Stop a running SOP monitoring instance."""
    if _state_machine is None:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    if _state_machine.get_instance(sop_id) is None:
        raise HTTPException(
            status_code=404, detail=f"No active instance for SOP '{sop_id}'"
        )

    _state_machine.stop_sop(sop_id)
    await _broadcast_state(sop_id, None)
    return {"status": "stopped", "sop_id": sop_id}


async def _broadcast_state(sop_id: str, state: dict | None):
    """Tell connected clients that the set of active SOPs changed."""
    try:
        from backend.api.ws import broadcast_event

        await broadcast_event("sop_state", {"sop_id": sop_id, "state": state})
    except Exception as e:  # broadcasting must never break the request
        logger.debug(f"Failed to broadcast SOP state: {e}")


@router.get("/sop/{sop_id}/state")
async def get_sop_state(sop_id: str):
    """Get state of a specific SOP instance."""
    if _state_machine is None:
        raise HTTPException(status_code=503, detail="Monitor not initialized")
    instance = _state_machine.get_instance(sop_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"No active instance for SOP '{sop_id}'")
    return instance.get_state_dict()


@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Get recent alerts."""
    if _alert_manager is None:
        return {"alerts": []}
    return {"alerts": _alert_manager.get_recent_alerts(limit)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    ok = _alert_manager.acknowledge(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/records")
async def get_records(
    limit: int = Query(default=100, le=1000),
    sop_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Query operation records from database."""
    query = db.query(OperationRecord).order_by(OperationRecord.timestamp.desc())
    if sop_id:
        query = query.filter(OperationRecord.sop_id == sop_id)
    records = query.limit(limit).all()
    return {
        "records": [
            {
                "id": r.id,
                "sop_id": r.sop_id,
                "step_id": r.step_id,
                "step_name": r.step_name,
                "status": r.status,
                "confidence": r.confidence,
                "details": r.details,
                "screenshot_path": r.screenshot_path,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in records
        ]
    }


@router.get("/records/export")
async def export_records(
    sop_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Export operation records as CSV download."""
    query = db.query(OperationRecord).order_by(OperationRecord.timestamp.desc())
    if sop_id:
        query = query.filter(OperationRecord.sop_id == sop_id)
    records = query.limit(10000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "SOP ID", "Step ID", "Step Name", "Status", "Confidence", "Details", "Timestamp"])
    for r in records:
        writer.writerow([
            r.id,
            r.sop_id,
            r.step_id,
            r.step_name,
            r.status,
            f"{r.confidence:.3f}",
            r.details or "",
            r.timestamp.isoformat() if r.timestamp else "",
        ])

    output.seek(0)
    filename = f"records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/detection/candidates")
async def get_detection_candidates():
    """Get top-3 candidate steps based on latest detection.

    Returns the best-matching SOP steps ranked by confidence,
    useful for showing what the system "thinks" is happening.
    """
    return {"candidates": _latest_candidates[:3]}
