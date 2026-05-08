"""SOP CRUD manager: load, save, list SOP definitions."""

import logging
import re
from pathlib import Path

import yaml

from backend.config import settings
from backend.sop.schema import SopDefinition, SopStep, StepRule

logger = logging.getLogger(__name__)

_SOP_ID_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_sop_id(sop_id: str):
    """Reject sop_id values that could cause path traversal."""
    if not sop_id or not _SOP_ID_RE.match(sop_id):
        raise ValueError(f"Invalid SOP ID: {sop_id!r}")


class SopManager:
    """Manages SOP definition YAML files on disk."""

    def __init__(self, sop_dir: str | None = None):
        self.sop_dir = Path(sop_dir or settings.sop_dir)
        self.sop_dir.mkdir(parents=True, exist_ok=True)

    def list_sops(self) -> list[dict]:
        """List all SOP definitions (metadata only)."""
        results = []
        for f in sorted(self.sop_dir.glob("*.yaml")):
            try:
                sop = self.load(f.stem)
                results.append({
                    "sop_id": sop.sop_id,
                    "name": sop.name,
                    "version": sop.version,
                    "step_count": len(sop.steps),
                })
            except Exception as e:
                logger.warning(f"Failed to load SOP {f}: {e}")
        return results

    def load(self, sop_id: str) -> SopDefinition:
        """Load an SOP definition from YAML file."""
        validate_sop_id(sop_id)
        path = self.sop_dir / f"{sop_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"SOP not found: {sop_id}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return self._parse_definition(data)

    def save(self, sop: SopDefinition):
        """Save an SOP definition to YAML file."""
        validate_sop_id(sop.sop_id)
        path = self.sop_dir / f"{sop.sop_id}.yaml"
        data = {
            "sop_id": sop.sop_id,
            "name": sop.name,
            "version": sop.version,
            "description": sop.description,
            "max_total_duration": sop.max_total_duration,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "description": s.description,
                    "order": s.order,
                    "estimated_duration": s.estimated_duration,
                    "timeout": s.timeout,
                    "is_optional": s.is_optional,
                    "rule": {
                        "expected_objects": s.rule.expected_objects,
                        "expected_gestures": s.rule.expected_gestures,
                        "min_confidence": s.rule.min_confidence,
                        "required_count": s.rule.required_count,
                        "confirm_frames": s.rule.confirm_frames,
                    },
                }
                for s in sop.steps
            ],
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info(f"Saved SOP: {sop.sop_id}")

    def delete(self, sop_id: str) -> bool:
        """Delete an SOP definition file."""
        validate_sop_id(sop_id)
        path = self.sop_dir / f"{sop_id}.yaml"
        if path.exists():
            path.unlink()
            logger.info(f"Deleted SOP: {sop_id}")
            return True
        return False

    def _parse_definition(self, data: dict) -> SopDefinition:
        """Parse raw YAML dict into SopDefinition."""
        steps = []
        for s in data.get("steps", []):
            rule_data = s.get("rule", {})
            step = SopStep(
                step_id=s["step_id"],
                name=s["name"],
                description=s.get("description", ""),
                order=s.get("order", 0),
                estimated_duration=s.get("estimated_duration", 0),
                timeout=s.get("timeout", 300),
                is_optional=s.get("is_optional", False),
                rule=StepRule(
                    expected_objects=rule_data.get("expected_objects", []),
                    expected_gestures=rule_data.get("expected_gestures", []),
                    min_confidence=rule_data.get("min_confidence", 0.5),
                    required_count=rule_data.get("required_count", 1),
                    confirm_frames=rule_data.get("confirm_frames", 3),
                ),
            )
            steps.append(step)

        return SopDefinition(
            sop_id=data["sop_id"],
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            steps=steps,
            max_total_duration=data.get("max_total_duration", 3600),
        )
