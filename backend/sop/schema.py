"""SOP YAML schema definitions using Pydantic."""

from pydantic import BaseModel, Field


class StepRule(BaseModel):
    """Detection rule for a single SOP step."""
    expected_objects: list[str] = Field(default_factory=list)
    min_confidence: float = 0.5
    required_count: int = 1
    confirm_frames: int = 3  # consecutive matching frames needed to confirm step completion


class SopStep(BaseModel):
    """A single step in an SOP procedure."""
    step_id: str
    name: str
    description: str = ""
    order: int
    estimated_duration: int = 0  # seconds
    timeout: int = 300  # seconds, max time allowed for this step
    rule: StepRule = Field(default_factory=StepRule)
    is_optional: bool = False


class SopDefinition(BaseModel):
    """Full SOP definition loaded from YAML."""
    sop_id: str
    name: str
    version: str = "1.0"
    description: str = ""
    steps: list[SopStep]
    max_total_duration: int = 3600  # seconds
