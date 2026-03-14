"""Tests for EventStore -> EventBus integration (EVT-1.3)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.event_bus.in_memory import InMemoryEventBus
from lintel.event_store.in_memory import InMemoryEventStore


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
        payload={"key": "value"},
        idempotency_key=None,
    )


class _RecordingHandler:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def handle(self, event: EventEnvelope) -> None:
        self.events.append(event)


class TestEventStoreBusIntegration:
    async def test_append_publishes_to_bus(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)
        handler = _RecordingHandler()
        await bus.subscribe(frozenset({"TestEvent"}), handler)

        event = _make_event("TestEvent")
        await store.append(stream_id="test-stream", events=[event])
        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_id == event.event_id

    async def test_append_multiple_events_publishes_all(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)
        handler = _RecordingHandler()
        await bus.subscribe(frozenset(), handler)

        events = [_make_event("TypeA"), _make_event("TypeB")]
        await store.append(stream_id="test-stream", events=events)
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2

    async def test_append_without_bus_still_works(self) -> None:
        store = InMemoryEventStore()
        event = _make_event("TestEvent")
        await store.append(stream_id="test-stream", events=[event])

        stored = await store.read_stream("test-stream")
        assert len(stored) == 1

    async def test_set_event_bus_after_construction(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore()
        handler = _RecordingHandler()
        await bus.subscribe(frozenset({"TestEvent"}), handler)

        store.set_event_bus(bus)

        event = _make_event("TestEvent")
        await store.append(stream_id="test-stream", events=[event])
        await asyncio.sleep(0.01)

        assert len(handler.events) == 1

    async def test_bus_failure_does_not_fail_append(self) -> None:
        """If bus publish fails, the event should still be persisted."""

        class _FailingBus:
            async def publish(self, event: EventEnvelope) -> None:
                msg = "bus failure"
                raise RuntimeError(msg)

        store = InMemoryEventStore(event_bus=_FailingBus())  # type: ignore[arg-type]
        event = _make_event("TestEvent")
        await store.append(stream_id="test-stream", events=[event])

        stored = await store.read_stream("test-stream")
        assert len(stored) == 1
