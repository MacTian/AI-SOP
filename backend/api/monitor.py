"""Monitoring data API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.record import OperationRecord

router = APIRouter(prefix="/api/monitor", tags=["Monitor"])

# These will be set by main.py after engine initialization
_state_machine = None
_alert_manager = None


def set_state_machine(sm):
    global _state_machine
    _state_machine = sm


def set_alert_manager(am):
    global _alert_manager
    _alert_manager = am


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
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in records
        ]
    }
