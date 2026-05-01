"""Tests for SOP schema definitions."""

from backend.sop.schema import SopDefinition, SopStep, StepRule


def test_step_rule_defaults():
    rule = StepRule()
    assert rule.expected_objects == []
    assert rule.min_confidence == 0.5
    assert rule.required_count == 1


def test_step_rule_custom():
    rule = StepRule(expected_objects=["hand", "tool"], min_confidence=0.7, required_count=2)
    assert rule.expected_objects == ["hand", "tool"]
    assert rule.min_confidence == 0.7
    assert rule.required_count == 2


def test_sop_step():
    step = SopStep(step_id="s1", name="Test Step", order=0)
    assert step.step_id == "s1"
    assert step.name == "Test Step"
    assert step.timeout == 300
    assert step.is_optional is False


def test_sop_definition():
    steps = [
        SopStep(step_id="s1", name="Step 1", order=0),
        SopStep(step_id="s2", name="Step 2", order=1),
    ]
    sop = SopDefinition(sop_id="test", name="Test SOP", steps=steps)
    assert sop.sop_id == "test"
    assert len(sop.steps) == 2
    assert sop.max_total_duration == 3600
