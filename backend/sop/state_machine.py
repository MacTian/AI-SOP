"""SOP state machine engine: tracks progress through SOP steps."""

import logging
import time
from enum import Enum

from backend.sop.schema import SopDefinition, SopStep
from backend.extractor.event import SopEvent

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    ERROR = "error"


class SopInstance:
    """Runtime state for a single SOP execution instance."""

    def __init__(self, definition: SopDefinition, strict_order: bool = False):
        self.definition = definition
        self.strict_order = strict_order
        self.current_step_index: int = 0
        self.step_statuses: dict[str, StepStatus] = {
            step.step_id: StepStatus.PENDING for step in definition.steps
        }
        self.started_at: float = time.time()
        self.completed_at: float | None = None
        self._step_start_times: dict[str, float] = {}
        self._consecutive_hits: dict[str, int] = {
            step.step_id: 0 for step in definition.steps
        }

    @property
    def current_step(self) -> SopStep | None:
        if 0 <= self.current_step_index < len(self.definition.steps):
            return self.definition.steps[self.current_step_index]
        return None

    @property
    def is_complete(self) -> bool:
        return all(
            s in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in self.step_statuses.values()
        )

    @property
    def progress(self) -> float:
        """Return progress as 0.0 to 1.0."""
        total = len(self.step_statuses)
        if total == 0:
            return 1.0
        done = sum(
            1 for s in self.step_statuses.values()
            if s in (StepStatus.COMPLETED, StepStatus.SKIPPED)
        )
        return done / total

    def start_step(self, step_id: str):
        """Mark a step as actively being performed."""
        if step_id in self.step_statuses:
            self.step_statuses[step_id] = StepStatus.ACTIVE
            self._step_start_times[step_id] = time.time()
            logger.info(f"SOP {self.definition.sop_id}: step {step_id} now ACTIVE")

    def complete_step(self, step_id: str):
        """Mark a step as completed and advance to next."""
        if step_id in self.step_statuses:
            self.step_statuses[step_id] = StepStatus.COMPLETED
            logger.info(f"SOP {self.definition.sop_id}: step {step_id} COMPLETED")
            self._advance()

    def _advance(self):
        """Move to the next pending step."""
        for i, step in enumerate(self.definition.steps):
            if self.step_statuses[step.step_id] == StepStatus.PENDING:
                self.current_step_index = i
                self.start_step(step.step_id)
                return
        # No more pending steps
        self.completed_at = time.time()
        logger.info(f"SOP {self.definition.sop_id} fully completed")

    def check_timeouts(self) -> list[str]:
        """Check for timed-out steps. Returns list of timed-out step IDs."""
        now = time.time()
        timed_out = []
        for step in self.definition.steps:
            if self.step_statuses[step.step_id] == StepStatus.ACTIVE:
                start = self._step_start_times.get(step.step_id, self.started_at)
                if now - start > step.timeout:
                    self.step_statuses[step.step_id] = StepStatus.TIMEOUT
                    timed_out.append(step.step_id)
                    logger.warning(f"SOP {self.definition.sop_id}: step {step.step_id} TIMEOUT")
        return timed_out

    def _get_confirm_frames(self, step_id: str) -> int:
        """Get the confirm_frames threshold for a step."""
        for step in self.definition.steps:
            if step.step_id == step_id:
                return step.rule.confirm_frames
        return 3  # fallback default

    def process_event(self, event: SopEvent) -> bool:
        """Process a detected event. Returns True if it caused a state change.

        Hit-frame confirmation: an ACTIVE step only completes after
        `confirm_frames` consecutive matching detections.

        When strict_order is enabled, events for non-current steps are rejected
        to prevent operators from skipping ahead.
        """
        if event.sop_id != self.definition.sop_id:
            return False

        step_id = event.step_id
        if step_id not in self.step_statuses:
            return False

        # Strict order: reject events for steps that aren't the current one
        if self.strict_order and self.current_step:
            if step_id != self.current_step.step_id:
                logger.debug(
                    f"SOP {self.definition.sop_id}: strict_order rejecting "
                    f"event for {step_id} (current: {self.current_step.step_id})"
                )
                return False

        current_status = self.step_statuses[step_id]
        if current_status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
            return False  # Already done

        if event.status == "detected":
            if current_status == StepStatus.PENDING:
                self.start_step(step_id)
                self._consecutive_hits[step_id] = 1
                return True
            elif current_status == StepStatus.ACTIVE:
                self._consecutive_hits[step_id] += 1
                confirm_needed = self._get_confirm_frames(step_id)
                if self._consecutive_hits[step_id] >= confirm_needed:
                    self.complete_step(step_id)
                    return True
                else:
                    logger.debug(
                        f"SOP {self.definition.sop_id}: step {step_id} hit "
                        f"{self._consecutive_hits[step_id]}/{confirm_needed}"
                    )
                    return False

        return False

    def reset_step_hits(self, step_id: str):
        """Reset consecutive hit counter for a step (e.g. on missed detection)."""
        if step_id in self._consecutive_hits:
            self._consecutive_hits[step_id] = 0

    def get_state_dict(self) -> dict:
        """Return serializable state snapshot."""
        # Build per-step hit progress info
        step_hit_progress = {}
        for step in self.definition.steps:
            sid = step.step_id
            confirm = step.rule.confirm_frames
            step_hit_progress[sid] = {
                "hits": self._consecutive_hits.get(sid, 0),
                "required": confirm,
            }

        return {
            "sop_id": self.definition.sop_id,
            "sop_name": self.definition.name,
            "current_step_index": self.current_step_index,
            "current_step_name": self.current_step.name if self.current_step else None,
            "step_statuses": {k: v.value for k, v in self.step_statuses.items()},
            "step_hit_progress": step_hit_progress,
            "progress": round(self.progress, 3),
            "is_complete": self.is_complete,
            "elapsed_time": round(time.time() - self.started_at, 1),
        }


class StateMachineEngine:
    """Manages multiple SOP execution instances."""

    def __init__(self, strict_order: bool = False):
        self._instances: dict[str, SopInstance] = {}
        self._strict_order = strict_order

    def start_sop(self, definition: SopDefinition) -> SopInstance:
        """Start a new SOP execution instance."""
        instance = SopInstance(definition, strict_order=self._strict_order)
        # Auto-start first step
        if definition.steps:
            first_step_id = definition.steps[0].step_id
            instance.start_step(first_step_id)
            instance._consecutive_hits[first_step_id] = 1
        self._instances[definition.sop_id] = instance
        logger.info(f"Started SOP instance: {definition.sop_id}")
        return instance

    def stop_sop(self, sop_id: str):
        """Stop and remove an SOP instance."""
        self._instances.pop(sop_id, None)
        logger.info(f"Stopped SOP instance: {sop_id}")

    def get_instance(self, sop_id: str) -> SopInstance | None:
        return self._instances.get(sop_id)

    def get_all_states(self) -> list[dict]:
        """Return state dicts for all active SOP instances."""
        return [inst.get_state_dict() for inst in self._instances.values()]

    def process_event(self, event: SopEvent) -> bool:
        """Route an event to the appropriate SOP instance."""
        instance = self._instances.get(event.sop_id)
        if instance:
            return instance.process_event(event)
        return False

    def check_all_timeouts(self) -> dict[str, list[str]]:
        """Check timeouts for all instances. Returns {sop_id: [timed_out_steps]}."""
        result = {}
        for sop_id, instance in self._instances.items():
            timed_out = instance.check_timeouts()
            if timed_out:
                result[sop_id] = timed_out
        return result
