"""Training API: start/stop training, get results, save SOP."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/training", tags=["Training"])

# Will be set by main.py
_session = None
_analyzer = None
_sop_manager = None


def set_session(session):
    global _session
    _session = session


def set_analyzer(analyzer):
    global _analyzer
    _analyzer = analyzer


def set_sop_manager(manager):
    global _sop_manager
    _sop_manager = manager


class TrainingStartRequest(BaseModel):
    sop_name: str = "New SOP"
    sop_description: str = ""


class StepUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    expected_objects: list[str] | None = None
    min_confidence: float | None = None
    timeout: int | None = None
    order: int | None = None


class SaveSopRequest(BaseModel):
    sop_id: str
    name: str
    version: str = "1.0"
    description: str = ""


# Store analyzed steps temporarily
_analyzed_steps: list[dict] = []


@router.post("/start")
async def start_training(req: TrainingStartRequest):
    """Start a new training session (begin recording)."""
    if _session is None:
        return {"error": "Training not initialized"}

    ok = _session.start(sop_name=req.sop_name, sop_description=req.sop_description)
    if not ok:
        return {"error": "Training already in progress"}

    return {"status": "recording", "message": "Training started"}


@router.post("/stop")
async def stop_training():
    """Stop recording and analyze captured frames."""
    global _analyzed_steps

    if _session is None:
        return {"error": "Training not initialized"}

    ok = _session.stop()
    if not ok:
        return {"error": "No training in progress"}

    # Analyze frames
    frames = _session.get_frames()
    if not frames:
        _session.reset()
        return {"error": "No frames recorded"}

    _analyzed_steps = _analyzer.analyze(frames)

    # Update session state
    _session._state.status = "ready"

    return {
        "status": "ready",
        "steps_found": len(_analyzed_steps),
        "frame_count": len(frames),
        "duration": round(_session._state.duration, 1),
    }


@router.get("/status")
async def get_status():
    """Get current training session status."""
    if _session is None:
        return {"status": "idle"}
    return _session.get_state_dict()


@router.get("/result")
async def get_result():
    """Get analysis result (identified steps)."""
    if not _analyzed_steps:
        return {"error": "No analysis result available. Run training first."}

    # Return steps without internal fields
    clean_steps = []
    for step in _analyzed_steps:
        clean = {k: v for k, v in step.items() if not k.startswith("_")}
        clean_steps.append(clean)

    return {
        "steps": clean_steps,
        "total_steps": len(clean_steps),
    }


@router.put("/step/{step_id}")
async def update_step(step_id: str, req: StepUpdateRequest):
    """Update a step in the analysis result (manual adjustment)."""
    global _analyzed_steps

    for step in _analyzed_steps:
        if step["step_id"] == step_id:
            if req.name is not None:
                step["name"] = req.name
            if req.description is not None:
                step["description"] = req.description
            if req.expected_objects is not None:
                step["expected_objects"] = req.expected_objects
            if req.min_confidence is not None:
                step["min_confidence"] = req.min_confidence
            if req.timeout is not None:
                step["timeout"] = req.timeout
            if req.order is not None:
                step["order"] = req.order
            return {"status": "updated", "step": {k: v for k, v in step.items() if not k.startswith("_")}}

    return {"error": f"Step '{step_id}' not found"}


@router.delete("/step/{step_id}")
async def delete_step(step_id: str):
    """Delete a step from the analysis result."""
    global _analyzed_steps
    before = len(_analyzed_steps)
    _analyzed_steps = [s for s in _analyzed_steps if s["step_id"] != step_id]
    if len(_analyzed_steps) == before:
        return {"error": f"Step '{step_id}' not found"}

    # Re-number
    for i, step in enumerate(_analyzed_steps):
        step["step_id"] = f"auto_step_{i + 1}"
        step["order"] = i

    return {"status": "deleted", "remaining": len(_analyzed_steps)}


@router.post("/step/reorder")
async def reorder_steps(step_ids: list[str]):
    """Reorder steps by providing step_ids in desired order."""
    global _analyzed_steps

    id_map = {s["step_id"]: s for s in _analyzed_steps}
    reordered = []
    for i, sid in enumerate(step_ids):
        if sid in id_map:
            step = id_map[sid]
            step["order"] = i
            step["step_id"] = f"auto_step_{i + 1}"
            reordered.append(step)

    # Add any remaining steps not in the list
    for step in _analyzed_steps:
        if step["step_id"] not in id_map:
            step["order"] = len(reordered)
            step["step_id"] = f"auto_step_{len(reordered) + 1}"
            reordered.append(step)

    _analyzed_steps = reordered
    return {"status": "reordered", "steps": len(_analyzed_steps)}


@router.post("/save")
async def save_as_sop(req: SaveSopRequest):
    """Save the analyzed steps as a formal SOP definition."""
    global _analyzed_steps

    if not _analyzed_steps:
        return {"error": "No steps to save"}

    if _sop_manager is None:
        return {"error": "SOP manager not initialized"}

    from backend.sop.schema import SopDefinition, SopStep, StepRule

    steps = []
    for s in _analyzed_steps:
        step = SopStep(
            step_id=s["step_id"],
            name=s["name"],
            description=s.get("description", ""),
            order=s.get("order", 0),
            estimated_duration=s.get("estimated_duration", 30),
            timeout=s.get("timeout", 120),
            rule=StepRule(
                expected_objects=s.get("expected_objects", []),
                min_confidence=s.get("min_confidence", 0.5),
                required_count=s.get("required_count", 1),
            ),
        )
        steps.append(step)

    sop = SopDefinition(
        sop_id=req.sop_id,
        name=req.name,
        version=req.version,
        description=req.description,
        steps=steps,
    )
    _sop_manager.save(sop)

    # Reset training session
    if _session:
        _session.reset()
    _analyzed_steps = []

    return {"status": "saved", "sop_id": req.sop_id, "step_count": len(steps)}


@router.post("/reset")
async def reset_training():
    """Reset training session."""
    global _analyzed_steps
    if _session:
        _session.reset()
    _analyzed_steps = []
    return {"status": "reset"}
