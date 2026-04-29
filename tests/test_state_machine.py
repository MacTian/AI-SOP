"""Tests for SOP state machine."""

import time
from backend.sop.schema import SopDefinition, SopStep, StepRule
from backend.sop.state_machine import SopInstance, StateMachineEngine, StepStatus
from backend.extractor.event import SopEvent


def make_test_sop():
    """Create a test SOP definition."""
    steps = [
        SopStep(step_id="s1", name="Step 1", order=0, timeout=10,
                rule=StepRule(expected_objects=["hand"])),
        SopStep(step_id="s2", name="Step 2", order=1, timeout=10,
                rule=StepRule(expected_objects=["tool"])),
        SopStep(step_id="s3", name="Step 3", order=2, timeout=10,
                rule=StepRule(expected_objects=["box"])),
    ]
    return SopDefinition(sop_id="test", name="Test SOP", steps=steps)


def test_instance_initial_state():
    sop = make_test_sop()
    inst = SopInstance(sop)
    assert inst.current_step is not None
    assert inst.current_step.step_id == "s1"
    assert inst.progress == 0.0
    assert inst.is_complete is False


def test_instance_start_step():
    sop = make_test_sop()
    inst = SopInstance(sop)
    inst.start_step("s1")
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE


def test_instance_complete_step():
    sop = make_test_sop()
    inst = SopInstance(sop)
    inst.start_step("s1")
    inst.complete_step("s1")
    assert inst.step_statuses["s1"] == StepStatus.COMPLETED
    # Should auto-advance to s2
    assert inst.current_step.step_id == "s2"
    assert inst.step_statuses["s2"] == StepStatus.ACTIVE


def test_instance_full_completion():
    sop = make_test_sop()
    inst = SopInstance(sop)
    for step in sop.steps:
        inst.start_step(step.step_id)
        inst.complete_step(step.step_id)
    assert inst.is_complete is True
    assert inst.progress == 1.0


def test_instance_process_event():
    sop = make_test_sop()
    inst = SopInstance(sop)
    event = SopEvent(sop_id="test", step_id="s1", step_name="Step 1", status="detected")
    changed = inst.process_event(event)
    assert changed is True
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE


def test_instance_wrong_sop_event():
    sop = make_test_sop()
    inst = SopInstance(sop)
    event = SopEvent(sop_id="other", step_id="s1", step_name="Step 1", status="detected")
    changed = inst.process_event(event)
    assert changed is False


def test_instance_get_state_dict():
    sop = make_test_sop()
    inst = SopInstance(sop)
    state = inst.get_state_dict()
    assert state["sop_id"] == "test"
    assert state["sop_name"] == "Test SOP"
    assert "step_statuses" in state
    assert "progress" in state


def test_state_machine_engine():
    engine = StateMachineEngine()
    sop = make_test_sop()
    inst = engine.start_sop(sop)
    assert inst is not None
    assert engine.get_instance("test") is not None
    assert len(engine.get_all_states()) == 1


def test_state_machine_stop():
    engine = StateMachineEngine()
    sop = make_test_sop()
    engine.start_sop(sop)
    engine.stop_sop("test")
    assert engine.get_instance("test") is None


def test_state_machine_process_event():
    engine = StateMachineEngine()
    sop = make_test_sop()
    engine.start_sop(sop)
    event = SopEvent(sop_id="test", step_id="s1", step_name="Step 1", status="detected")
    changed = engine.process_event(event)
    assert changed is True


def test_state_machine_wrong_event():
    engine = StateMachineEngine()
    sop = make_test_sop()
    engine.start_sop(sop)
    event = SopEvent(sop_id="nonexistent", step_id="s1", step_name="Step 1", status="detected")
    changed = engine.process_event(event)
    assert changed is False


def test_instance_timeout_check():
    sop = make_test_sop()
    # Use very short timeout
    sop.steps[0].timeout = 0
    inst = SopInstance(sop)
    inst.start_step("s1")
    time.sleep(0.01)
    timed_out = inst.check_timeouts()
    assert "s1" in timed_out
    assert inst.step_statuses["s1"] == StepStatus.TIMEOUT
