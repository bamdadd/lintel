"""Tests for the Delivery Loop Manager."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from lintel.contracts.events import (
    DeliveryLoopCompleted,
    DeliveryLoopPhaseTransitioned,
    DeliveryLoopStarted,
    EventEnvelope,
)
from lintel.domain.delivery_loop.loop_manager import DeliveryLoopManager


def _make_event(event_type: str, payload: dict[str, Any] | None = None) -> EventEnvelope:
    """Create a minimal event envelope for testing."""
    return EventEnvelope(
        event_type=event_type,
        payload=payload or {},
        correlation_id=uuid4(),
    )


class FakeEventBus:
    """Captures published events for assertions."""

    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)

    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: object,
    ) -> str:
        return "sub-1"

    async def unsubscribe(self, subscription_id: str) -> None:
        pass


class TestDeliveryLoopStart:
    async def test_work_item_created_starts_loop(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        event = _make_event(
            "WorkItemCreated",
            {"work_item_id": "wi-1", "project_id": "proj-1"},
        )
        await mgr.handle(event)

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.current_phase == "desire"
        assert loop.project_id == "proj-1"
        assert loop.started_at is not None
        assert loop.completed_at is None

    async def test_emits_delivery_loop_started(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event("WorkItemCreated", {"work_item_id": "wi-1", "project_id": "p1"})
        )

        started = [e for e in bus.published if isinstance(e, DeliveryLoopStarted)]
        assert len(started) == 1
        assert started[0].payload["work_item_id"] == "wi-1"
        assert started[0].payload["phase"] == "desire"

    async def test_idempotent_start(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        event = _make_event("WorkItemCreated", {"work_item_id": "wi-1"})
        await mgr.handle(event)
        await mgr.handle(event)

        assert len([e for e in bus.published if isinstance(e, DeliveryLoopStarted)]) == 1

    async def test_custom_phase_sequence(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event(
                "WorkItemCreated",
                {
                    "work_item_id": "wi-1",
                    "phase_sequence": ["desire", "develop", "deploy"],
                },
            )
        )

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.phase_sequence == ("desire", "develop", "deploy")


class TestPhaseTransition:
    async def test_pipeline_started_transitions_to_develop(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event("WorkItemCreated", {"work_item_id": "wi-1"})
        )
        await mgr.handle(
            _make_event("PipelineRunStarted", {"work_item_id": "wi-1"})
        )

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.current_phase == "develop"

    async def test_emits_phase_transitioned(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event("WorkItemCreated", {"work_item_id": "wi-1"})
        )
        await mgr.handle(
            _make_event("PipelineRunStarted", {"work_item_id": "wi-1"})
        )

        transitioned = [e for e in bus.published if isinstance(e, DeliveryLoopPhaseTransitioned)]
        assert len(transitioned) == 1
        assert transitioned[0].payload["from_phase"] == "desire"
        assert transitioned[0].payload["to_phase"] == "develop"
        assert transitioned[0].payload["is_rework"] is False

    async def test_skip_if_no_loop(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event("PipelineRunStarted", {"work_item_id": "unknown"})
        )

        assert len(bus.published) == 0

    async def test_skip_if_already_in_phase(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event("WorkItemCreated", {"work_item_id": "wi-1"})
        )
        await mgr.handle(
            _make_event("PipelineRunStarted", {"work_item_id": "wi-1"})
        )
        bus.published.clear()
        await mgr.handle(
            _make_event("PipelineRunStarted", {"work_item_id": "wi-1"})
        )

        assert len(bus.published) == 0

    async def test_rework_detected(self) -> None:
        """Going from review back to develop is rework."""
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(_make_event("WorkItemCreated", {"work_item_id": "wi-1"}))
        await mgr.handle(_make_event("PipelineRunStarted", {"work_item_id": "wi-1"}))
        await mgr.handle(_make_event("PRCreated", {"work_item_id": "wi-1"}))
        # Rework: go back to develop
        await mgr.handle(_make_event("PipelineRunStarted", {"work_item_id": "wi-1"}))

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.current_phase == "develop"
        rework_transitions = [t for t in loop.phase_history if t.is_rework]
        assert len(rework_transitions) == 1

    async def test_phase_not_in_sequence_skipped(self) -> None:
        """Custom sequence without 'review' should skip PRCreated."""
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event(
                "WorkItemCreated",
                {
                    "work_item_id": "wi-1",
                    "phase_sequence": ["desire", "develop", "deploy"],
                },
            )
        )
        await mgr.handle(_make_event("PipelineRunStarted", {"work_item_id": "wi-1"}))
        bus.published.clear()
        await mgr.handle(_make_event("PRCreated", {"work_item_id": "wi-1"}))

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.current_phase == "develop"  # unchanged
        assert len(bus.published) == 0


class TestLoopCompletion:
    async def test_last_phase_completes_loop(self) -> None:
        """Reaching the learn phase should mark the loop as completed."""
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        # Use a short sequence for simplicity.
        await mgr.handle(
            _make_event(
                "WorkItemCreated",
                {
                    "work_item_id": "wi-1",
                    "phase_sequence": ["desire", "develop"],
                },
            )
        )
        await mgr.handle(_make_event("PipelineRunStarted", {"work_item_id": "wi-1"}))

        loop = mgr.get_loop("wi-1")
        assert loop is not None
        assert loop.completed_at is not None

        completed = [e for e in bus.published if isinstance(e, DeliveryLoopCompleted)]
        assert len(completed) == 1
        assert completed[0].payload["work_item_id"] == "wi-1"
        assert "total_duration_ms" in completed[0].payload
        assert "rework_count" in completed[0].payload

    async def test_completed_loop_ignores_events(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)

        await mgr.handle(
            _make_event(
                "WorkItemCreated",
                {"work_item_id": "wi-1", "phase_sequence": ["desire", "develop"]},
            )
        )
        await mgr.handle(_make_event("PipelineRunStarted", {"work_item_id": "wi-1"}))
        bus.published.clear()

        # Should be ignored — loop already completed.
        await mgr.handle(_make_event("PRCreated", {"work_item_id": "wi-1"}))
        assert len(bus.published) == 0


class TestQueryHelpers:
    async def test_get_all_loops(self) -> None:
        mgr = DeliveryLoopManager()
        await mgr.handle(_make_event("WorkItemCreated", {"work_item_id": "wi-1"}))
        await mgr.handle(_make_event("WorkItemCreated", {"work_item_id": "wi-2"}))

        loops = mgr.get_all_loops()
        assert len(loops) == 2

    async def test_get_loop_none(self) -> None:
        mgr = DeliveryLoopManager()
        assert mgr.get_loop("nonexistent") is None


class TestStartStop:
    async def test_start_subscribes(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)
        await mgr.start()
        assert mgr._subscription_id == "sub-1"

    async def test_stop_unsubscribes(self) -> None:
        bus = FakeEventBus()
        mgr = DeliveryLoopManager(event_bus=bus)
        await mgr.start()
        await mgr.stop()
        assert mgr._subscription_id is None

    async def test_no_bus_noop(self) -> None:
        mgr = DeliveryLoopManager()
        await mgr.start()  # should not raise
        await mgr.stop()
