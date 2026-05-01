"""Monitoring data API endpoints."""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.record import OperationRecord
from backend.api.auth import get_current_user

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


@router.get("/sop/{sop_id}/state")
async def get_sop_state(sop_id: str):
    """Get state of a specific SOP instance."""
    if _state_machine is None:
        return {"error": "Monitor not initialized"}
    instance = _state_machine.get_instance(sop_id)
    if instance is None:
        return {"error": f"No active instance for SOP '{sop_id}'"}
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
        return {"error": "Alert manager not initialized"}
    ok = _alert_manager.acknowledge(alert_id)
    if not ok:
        return {"error": f"Alert '{alert_id}' not found"}
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
