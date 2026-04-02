"""Loop controller for continuous autonomous workflow execution (REQ-034.7)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from lintel.domain.autonomous.types import AutonomousLoop, LoopStatus

if TYPE_CHECKING:
    from lintel.domain.autonomous.types import LoopConfig, LoopIteration


class LoopController:
    """Manages lifecycle of autonomous loops."""

    def __init__(self) -> None:
        self._loops: dict[str, AutonomousLoop] = {}

    def start(self, config: LoopConfig) -> AutonomousLoop:
        """Start a new autonomous loop from the given configuration."""
        loop = AutonomousLoop(
            loop_id=config.loop_id,
            config=config,
            status=LoopStatus.RUNNING,
        )
        self._loops[config.loop_id] = loop
        return loop

    def pause(self, loop_id: str) -> AutonomousLoop:
        """Pause a running loop."""
        loop = self._get(loop_id)
        if loop.status != LoopStatus.RUNNING:
            msg = f"Cannot pause loop in status {loop.status}"
            raise ValueError(msg)
        updated = replace(loop, status=LoopStatus.PAUSED)
        self._loops[loop_id] = updated
        return updated

    def resume(self, loop_id: str) -> AutonomousLoop:
        """Resume a paused loop."""
        loop = self._get(loop_id)
        if loop.status != LoopStatus.PAUSED:
            msg = f"Cannot resume loop in status {loop.status}"
            raise ValueError(msg)
        updated = replace(loop, status=LoopStatus.RUNNING)
        self._loops[loop_id] = updated
        return updated

    def stop(self, loop_id: str) -> AutonomousLoop:
        """Stop a loop permanently."""
        loop = self._get(loop_id)
        if loop.status == LoopStatus.STOPPED:
            msg = "Loop is already stopped"
            raise ValueError(msg)
        updated = replace(loop, status=LoopStatus.STOPPED)
        self._loops[loop_id] = updated
        return updated

    def get_status(self, loop_id: str) -> AutonomousLoop:
        """Return the current state of a loop."""
        return self._get(loop_id)

    def record_iteration(self, loop_id: str, iteration: LoopIteration) -> AutonomousLoop:
        """Append a completed iteration to the loop history."""
        loop = self._get(loop_id)
        updated = replace(
            loop,
            iterations=(*loop.iterations, iteration),
            current_iteration=iteration.iteration_number,
        )
        self._loops[loop_id] = updated
        return updated

    def should_continue(self, loop_id: str) -> bool:
        """Determine whether the loop should execute another iteration."""
        loop = self._get(loop_id)
        if loop.status != LoopStatus.RUNNING:
            return False
        if loop.config.max_iterations is None:
            return True
        return loop.current_iteration < loop.config.max_iterations

    def _get(self, loop_id: str) -> AutonomousLoop:
        try:
            return self._loops[loop_id]
        except KeyError:
            msg = f"Loop {loop_id} not found"
            raise KeyError(msg) from None
