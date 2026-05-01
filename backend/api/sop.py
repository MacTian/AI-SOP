"""SOP REST API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.sop.schema import SopDefinition, SopStep, StepRule
from backend.sop.sop_manager import SopManager
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/sop", tags=["SOP"], dependencies=[Depends(get_current_user)])
manager = SopManager()

# Template manager points to templates subdirectory
_template_dir = Path(settings.sop_dir) / "templates"
_template_manager = SopManager(sop_dir=str(_template_dir))


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


# --- Template endpoints ---

@router.get("/templates/list")
async def list_templates():
    """List available SOP templates."""
    return {"templates": _template_manager.list_sops()}


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific template definition."""
    try:
        sop = _template_manager.load(template_id)
        return sop.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")


class UseTemplateRequest(BaseModel):
    sop_id: str
    name: str
    description: str = ""


@router.post("/templates/{template_id}/use")
async def use_template(template_id: str, req: UseTemplateRequest):
    """Create a new SOP based on a template."""
    try:
        template = _template_manager.load(template_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    # Create new SOP from template
    new_sop = SopDefinition(
        sop_id=req.sop_id,
        name=req.name,
        version="1.0",
        description=req.description or template.description,
        steps=template.steps,
        max_total_duration=template.max_total_duration,
    )
    manager.save(new_sop)
    return {"status": "ok", "sop_id": new_sop.sop_id, "step_count": len(new_sop.steps)}
