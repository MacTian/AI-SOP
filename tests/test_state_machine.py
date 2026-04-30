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
    # start_sop sets s1 ACTIVE with hits=1 (counts the activation as first hit).
    # With confirm_frames=3, need 2 more hits to complete.
    changed = engine.process_event(event)  # hit 2
    assert changed is False
    changed = engine.process_event(event)  # hit 3 → complete
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


# --- Hit-frame confirmation tests ---

def make_confirm_sop(confirm_frames=3):
    """Create a SOP with explicit confirm_frames settings."""
    steps = [
        SopStep(step_id="s1", name="Step 1", order=0, timeout=10,
                rule=StepRule(expected_objects=["hand"], confirm_frames=confirm_frames)),
        SopStep(step_id="s2", name="Step 2", order=1, timeout=10,
                rule=StepRule(expected_objects=["tool"], confirm_frames=confirm_frames)),
    ]
    return SopDefinition(sop_id="confirm_test", name="Confirm Test SOP", steps=steps)


def test_hit_frame_does_not_complete_before_threshold():
    """Step should NOT complete until confirm_frames consecutive hits."""
    sop = make_confirm_sop(confirm_frames=3)
    inst = SopInstance(sop)

    # First detected → PENDING → ACTIVE (not completed)
    event = SopEvent(sop_id="confirm_test", step_id="s1", step_name="Step 1", status="detected")
    changed = inst.process_event(event)
    assert changed is True
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE

    # Second detected → still ACTIVE (hit count = 2, need 3)
    changed = inst.process_event(event)
    assert changed is False
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE

    # Third detected → COMPLETED (hit count = 3, reached threshold)
    changed = inst.process_event(event)
    assert changed is True
    assert inst.step_statuses["s1"] == StepStatus.COMPLETED


def test_hit_frame_resets_on_missing_detection():
    """Consecutive hit counter should reset if step doesn't get detected."""
    sop = make_confirm_sop(confirm_frames=3)
    inst = SopInstance(sop)

    event = SopEvent(sop_id="confirm_test", step_id="s1", step_name="Step 1", status="detected")

    # First hit
    inst.process_event(event)
    assert inst._consecutive_hits["s1"] == 1

    # Simulate missed detection by resetting hits
    inst.reset_step_hits("s1")
    assert inst._consecutive_hits["s1"] == 0

    # Need 3 more hits to complete
    inst.process_event(event)  # hit 1
    inst.process_event(event)  # hit 2
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE

    inst.process_event(event)  # hit 3 → complete
    assert inst.step_statuses["s1"] == StepStatus.COMPLETED


def test_hit_frame_with_confirm_frames_1():
    """With confirm_frames=1, first detection after ACTIVE should complete."""
    sop = make_confirm_sop(confirm_frames=1)
    inst = SopInstance(sop)

    event = SopEvent(sop_id="confirm_test", step_id="s1", step_name="Step 1", status="detected")
    # First detected → ACTIVE
    inst.process_event(event)
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE

    # Second detected → COMPLETED (only need 1 consecutive hit after ACTIVE)
    inst.process_event(event)
    assert inst.step_statuses["s1"] == StepStatus.COMPLETED


def test_hit_frame_progress_in_state_dict():
    """State dict should include step_hit_progress."""
    sop = make_confirm_sop(confirm_frames=5)
    inst = SopInstance(sop)

    state = inst.get_state_dict()
    assert "step_hit_progress" in state
    assert state["step_hit_progress"]["s1"]["hits"] == 0
    assert state["step_hit_progress"]["s1"]["required"] == 5

    # One hit
    event = SopEvent(sop_id="confirm_test", step_id="s1", step_name="Step 1", status="detected")
    inst.process_event(event)
    state = inst.get_state_dict()
    assert state["step_hit_progress"]["s1"]["hits"] == 1


# --- Strict order tests ---

def test_strict_order_rejects_non_current_step():
    """In strict_order mode, events for non-current steps should be rejected."""
    sop = make_test_sop()
    inst = SopInstance(sop, strict_order=True)

    # Current step is s1. Try to detect s2 — should be rejected.
    event_s2 = SopEvent(sop_id="test", step_id="s2", step_name="Step 2", status="detected")
    changed = inst.process_event(event_s2)
    assert changed is False
    assert inst.step_statuses["s2"] == StepStatus.PENDING


def test_strict_order_allows_current_step():
    """In strict_order mode, events for the current step should be accepted."""
    sop = make_test_sop()
    inst = SopInstance(sop, strict_order=True)

    event_s1 = SopEvent(sop_id="test", step_id="s1", step_name="Step 1", status="detected")
    changed = inst.process_event(event_s1)
    assert changed is True
    assert inst.step_statuses["s1"] == StepStatus.ACTIVE


def test_strict_order_engine():
    """StateMachineEngine with strict_order should propagate to instances."""
    engine = StateMachineEngine(strict_order=True)
    sop = make_test_sop()
    inst = engine.start_sop(sop)
    assert inst.strict_order is True

    # Try to detect s2 while s1 is current — should fail
    event_s2 = SopEvent(sop_id="test", step_id="s2", step_name="Step 2", status="detected")
    changed = engine.process_event(event_s2)
    assert changed is False


def test_non_strict_order_allows_non_current_step():
    """Without strict_order, events for non-current steps should be allowed."""
    sop = make_test_sop()
    inst = SopInstance(sop, strict_order=False)

    event_s2 = SopEvent(sop_id="test", step_id="s2", step_name="Step 2", status="detected")
    changed = inst.process_event(event_s2)
    assert changed is True
    assert inst.step_statuses["s2"] == StepStatus.ACTIVE
