"""Tests for ProjectionEngine subscribing to EventBus (EVT-1.4)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.event_bus.in_memory import InMemoryEventBus
from lintel.event_store.in_memory import InMemoryEventStore
from lintel.projections.engine import InMemoryProjectionEngine


def _make_event(event_type: str = "TestEvent") -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        schema_version=1,
        occurred_at=datetime.now(UTC),
        actor_type=ActorType.SYSTEM,
        actor_id="test",
        thread_ref=None,
        correlation_id=uuid4(),
        causation_id=None,
        payload={},
        idempotency_key=None,
    )


class _FakeProjection:
    def __init__(self, event_types: set[str], projection_name: str = "fake") -> None:
        self._handled_event_types = event_types
        self._name = projection_name
        self.projected: list[EventEnvelope] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def handled_event_types(self) -> set[str]:
        return self._handled_event_types

    async def project(self, event: EventEnvelope) -> None:
        self.projected.append(event)

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self.projected = list(events)

    def get_state(self) -> dict[str, object]:
        return {}

    def restore_state(self, state: dict[str, object]) -> None:
        pass


class TestProjectionEngineBusSubscription:
    async def test_engine_receives_events_via_bus(self) -> None:
        """End-to-end: store.append -> bus.publish -> engine.project -> projection."""
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)
        engine = InMemoryProjectionEngine(event_bus=bus)

        projection = _FakeProjection({"TestEvent"})
        await engine.register(projection)
        await engine.start()

        event = _make_event("TestEvent")
        await store.append(stream_id="test", events=[event])
        await asyncio.sleep(0.01)

        assert len(projection.projected) == 1
        assert projection.projected[0].event_id == event.event_id

    async def test_engine_filters_by_projection_event_types(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)
        engine = InMemoryProjectionEngine(event_bus=bus)

        projection = _FakeProjection({"TypeA"})
        await engine.register(projection)
        await engine.start()

        await store.append(stream_id="test", events=[_make_event("TypeA")])
        await store.append(stream_id="test", events=[_make_event("TypeB")])
        await asyncio.sleep(0.01)

        assert len(projection.projected) == 1
        assert projection.projected[0].event_type == "TypeA"

    async def test_multiple_projections_receive_events(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)
        engine = InMemoryProjectionEngine(event_bus=bus)

        proj_a = _FakeProjection({"TestEvent"})
        proj_b = _FakeProjection({"TestEvent"})
        await engine.register(proj_a)
        await engine.register(proj_b)
        await engine.start()

        await store.append(stream_id="test", events=[_make_event("TestEvent")])
        await asyncio.sleep(0.01)

        assert len(proj_a.projected) == 1
        assert len(proj_b.projected) == 1

    async def test_engine_stop_unsubscribes(self) -> None:
        bus = InMemoryEventBus()
        engine = InMemoryProjectionEngine(event_bus=bus)
        proj = _FakeProjection({"TestEvent"})
        await engine.register(proj)
        await engine.start()
        assert bus.subscription_count == 1

        await engine.stop()
        assert bus.subscription_count == 0

    async def test_engine_without_bus_still_works_manually(self) -> None:
        """Backward compat: direct project() calls still work without bus."""
        engine = InMemoryProjectionEngine()
        proj = _FakeProjection({"TestEvent"})
        await engine.register(proj)

        event = _make_event("TestEvent")
        await engine.project(event)

        assert len(proj.projected) == 1

    async def test_start_without_bus_is_noop(self) -> None:
        engine = InMemoryProjectionEngine()
        await engine.start()  # should not raise

    async def test_stop_without_bus_is_noop(self) -> None:
        engine = InMemoryProjectionEngine()
        await engine.stop()  # should not raise
