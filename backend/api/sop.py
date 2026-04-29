"""SOP REST API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.sop.schema import SopDefinition, SopStep, StepRule
from backend.sop.sop_manager import SopManager

router = APIRouter(prefix="/api/sop", tags=["SOP"])
manager = SopManager()


class SopCreateRequest(BaseModel):
    """Request body for creating/updating an SOP."""
    sop_id: str
    name: str
    version: str = "1.0"
    description: str = ""
    max_total_duration: int = 3600
    steps: list[dict]


@router.get("/list")
async def list_sops():
    """List all available SOP definitions."""
    return {"sops": manager.list_sops()}


@router.get("/{sop_id}")
async def get_sop(sop_id: str):
    """Get a specific SOP definition by ID."""
    try:
        sop = manager.load(sop_id)
        return sop.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' not found")


@router.post("/")
async def create_sop(req: SopCreateRequest):
    """Create or update an SOP definition."""
    steps = []
    for i, s in enumerate(req.steps):
        rule_data = s.get("rule", {})
        step = SopStep(
            step_id=s["step_id"],
            name=s["name"],
            description=s.get("description", ""),
            order=s.get("order", i),
            estimated_duration=s.get("estimated_duration", 0),
            timeout=s.get("timeout", 300),
            is_optional=s.get("is_optional", False),
            rule=StepRule(
                expected_objects=rule_data.get("expected_objects", []),
                min_confidence=rule_data.get("min_confidence", 0.5),
                required_count=rule_data.get("required_count", 1),
            ),
        )
        steps.append(step)

    sop = SopDefinition(
        sop_id=req.sop_id,
        name=req.name,
        version=req.version,
        description=req.description,
        steps=steps,
        max_total_duration=req.max_total_duration,
    )
    manager.save(sop)
    return {"status": "ok", "sop_id": sop.sop_id}


@router.delete("/{sop_id}")
async def delete_sop(sop_id: str):
    """Delete an SOP definition."""
    if not manager.delete(sop_id):
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' not found")
    return {"status": "deleted", "sop_id": sop_id}
