"""Delivery Loop Manager — subscribes to domain events and manages loop lifecycle.

Tracks work items through configurable phase sequences (desire → develop → review →
deploy → observe → learn) by observing domain events and transitioning phases
accordingly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from lintel.contracts.types import (
    DEFAULT_DELIVERY_PHASES,
    DeliveryLoop,
    PhaseTransitionRecord,
)
import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus

logger = structlog.get_logger()

# Map event types to the phase they trigger entry into.
EVENT_TO_PHASE: dict[str, str] = {
    "WorkItemCreated": "desire",
    "PipelineRunStarted": "develop",
    "PRCreated": "review",
    "HumanApprovalGranted": "deploy",
    "DeploymentSucceeded": "observe",
}

# Events the loop manager subscribes to.
SUBSCRIBED_EVENTS = frozenset(EVENT_TO_PHASE.keys())


class DeliveryLoopManager:
    """Subscribes to domain events and manages DeliveryLoop lifecycle.

    Implements the EventHandler protocol (``handle(event)``).
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._subscription_id: str | None = None
        # In-memory store keyed by work_item_id.
        self._loops: dict[str, DeliveryLoop] = {}

    async def start(self) -> None:
        """Subscribe to the event bus."""
        if self._event_bus is None:
            return
        self._subscription_id = await self._event_bus.subscribe(
            SUBSCRIBED_EVENTS,
            self,
        )
        logger.info("delivery_loop_manager_started", subscription_id=self._subscription_id)

    async def stop(self) -> None:
        """Unsubscribe from the event bus."""
        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — dispatched by the EventBus."""
        target_phase = EVENT_TO_PHASE.get(event.event_type)
        if target_phase is None:
            return

        work_item_id = self._extract_work_item_id(event)
        if not work_item_id:
            return

        if event.event_type == "WorkItemCreated":
            await self._start_loop(event, work_item_id)
        else:
            await self._transition_phase(event, work_item_id, target_phase)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_work_item_id(event: EventEnvelope) -> str:
        """Pull work_item_id from event payload."""
        return str(event.payload.get("work_item_id", ""))

    async def _start_loop(self, event: EventEnvelope, work_item_id: str) -> None:
        """Create a new delivery loop on WorkItemCreated."""
        if work_item_id in self._loops:
            return  # idempotent

        project_id = str(event.payload.get("project_id", ""))
        phase_sequence = self._resolve_phase_sequence(event)
        first_phase = phase_sequence[0] if phase_sequence else "desire"
        now = datetime.now(UTC)

        loop = DeliveryLoop(
            loop_id=str(uuid4()),
            work_item_id=work_item_id,
            project_id=project_id,
            phase_sequence=phase_sequence,
            current_phase=first_phase,
            phase_history=(
                PhaseTransitionRecord(
                    from_phase="",
                    to_phase=first_phase,
                    occurred_at=now,
                ),
            ),
            started_at=now,
        )
        self._loops[work_item_id] = loop

        if self._event_bus is not None:
            from lintel.contracts.events import DeliveryLoopStarted

            await self._event_bus.publish(
                DeliveryLoopStarted(
                    payload={
                        "loop_id": loop.loop_id,
                        "work_item_id": work_item_id,
                        "project_id": project_id,
                        "phase": first_phase,
                    },
                    correlation_id=event.correlation_id,
                )
            )

        logger.info(
            "delivery_loop_started",
            loop_id=loop.loop_id,
            work_item_id=work_item_id,
            phase=first_phase,
        )

    async def _transition_phase(
        self,
        event: EventEnvelope,
        work_item_id: str,
        target_phase: str,
    ) -> None:
        """Transition an existing loop to the target phase."""
        loop = self._loops.get(work_item_id)
        if loop is None or loop.completed_at is not None:
            return

        if target_phase not in loop.phase_sequence:
            return  # phase not in this loop's sequence

        if loop.current_phase == target_phase:
            return  # already in this phase

        now = datetime.now(UTC)
        from_phase = loop.current_phase

        # Detect rework (backward transition).
        current_idx = (
            loop.phase_sequence.index(from_phase) if from_phase in loop.phase_sequence else -1
        )
        target_idx = loop.phase_sequence.index(target_phase)
        is_rework = target_idx <= current_idx

        transition = PhaseTransitionRecord(
            from_phase=from_phase,
            to_phase=target_phase,
            occurred_at=now,
            is_rework=is_rework,
        )

        # Check if this is the last phase completing.
        is_last_phase = target_idx == len(loop.phase_sequence) - 1

        updated = DeliveryLoop(
            loop_id=loop.loop_id,
            work_item_id=loop.work_item_id,
            project_id=loop.project_id,
            phase_sequence=loop.phase_sequence,
            current_phase=target_phase,
            phase_history=(*loop.phase_history, transition),
            started_at=loop.started_at,
            completed_at=now if is_last_phase else None,
            learnings=loop.learnings,
        )
        self._loops[work_item_id] = updated

        if self._event_bus is not None:
            from lintel.contracts.events import DeliveryLoopPhaseTransitioned

            await self._event_bus.publish(
                DeliveryLoopPhaseTransitioned(
                    payload={
                        "loop_id": loop.loop_id,
                        "work_item_id": work_item_id,
                        "from_phase": from_phase,
                        "to_phase": target_phase,
                        "is_rework": is_rework,
                    },
                    correlation_id=event.correlation_id,
                )
            )

        if is_last_phase:
            await self._complete_loop(updated, event)

        logger.info(
            "delivery_loop_phase_transitioned",
            loop_id=loop.loop_id,
            from_phase=from_phase,
            to_phase=target_phase,
            is_rework=is_rework,
        )

    async def _complete_loop(self, loop: DeliveryLoop, event: EventEnvelope) -> None:
        """Emit DeliveryLoopCompleted with duration metrics."""
        if self._event_bus is None or loop.started_at is None:
            return

        duration_ms = (
            int((loop.completed_at - loop.started_at).total_seconds() * 1000)
            if loop.completed_at
            else 0
        )
        rework_count = sum(1 for t in loop.phase_history if t.is_rework)

        # Compute per-phase durations from history.
        phase_durations: dict[str, int] = {}
        for i in range(1, len(loop.phase_history)):
            prev = loop.phase_history[i - 1]
            curr = loop.phase_history[i]
            ms = int((curr.occurred_at - prev.occurred_at).total_seconds() * 1000)
            phase_durations[prev.to_phase] = phase_durations.get(prev.to_phase, 0) + ms

        from lintel.contracts.events import DeliveryLoopCompleted

        await self._event_bus.publish(
            DeliveryLoopCompleted(
                payload={
                    "loop_id": loop.loop_id,
                    "work_item_id": loop.work_item_id,
                    "project_id": loop.project_id,
                    "total_duration_ms": duration_ms,
                    "rework_count": rework_count,
                    "phase_durations": phase_durations,
                },
                correlation_id=event.correlation_id,
            )
        )

        logger.info(
            "delivery_loop_completed",
            loop_id=loop.loop_id,
            duration_ms=duration_ms,
            rework_count=rework_count,
        )

    @staticmethod
    def _resolve_phase_sequence(event: EventEnvelope) -> tuple[str, ...]:
        """Resolve phase sequence from event payload or use default."""
        seq = event.payload.get("phase_sequence")
        if isinstance(seq, (list, tuple)) and seq:
            return tuple(str(s) for s in seq)
        return DEFAULT_DELIVERY_PHASES

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_loop(self, work_item_id: str) -> DeliveryLoop | None:
        """Get the delivery loop for a work item."""
        return self._loops.get(work_item_id)

    def get_all_loops(self) -> list[DeliveryLoop]:
        """Get all tracked delivery loops."""
        return list(self._loops.values())
