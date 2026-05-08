"""Alert configuration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.alert.manager import AlertRule
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["Alerts"], dependencies=[Depends(get_current_user)])

# Will be set by main.py
_alert_manager = None


def set_alert_manager(am):
    global _alert_manager
    _alert_manager = am


class AlertRuleRequest(BaseModel):
    sop_id: str
    step_id: str
    level: str = "warning"
    escalation_count: int = 3
    cooldown: int = 0


@router.get("/rules")
async def get_rules():
    """Get all alert rules."""
    if _alert_manager is None:
        return {"rules": []}
    return {"rules": _alert_manager.get_rules()}


@router.post("/rules")
async def create_rule(req: AlertRuleRequest):
    """Create or update an alert rule."""
    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    rule = AlertRule(
        sop_id=req.sop_id,
        step_id=req.step_id,
        level=req.level,
        escalation_count=req.escalation_count,
        cooldown=req.cooldown,
    )
    _alert_manager.add_rule(rule)
    return {"status": "ok", "rule": req.model_dump()}


@router.delete("/rules/{sop_id}/{step_id}")
async def delete_rule(sop_id: str, step_id: str):
    """Delete an alert rule."""
    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    _alert_manager.remove_rule(sop_id, step_id)
    return {"status": "deleted"}


@router.post("/acknowledge-all")
async def acknowledge_all():
    """Acknowledge all unacknowledged alerts."""
    if _alert_manager is None:
        raise HTTPException(status_code=503, detail="Alert manager not initialized")
    count = _alert_manager.acknowledge_all()
    return {"status": "ok", "acknowledged": count}
