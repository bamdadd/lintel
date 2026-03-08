"""Unit tests for event subscription patterns (EVT-2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.infrastructure.event_bus.in_memory import InMemoryEventBus
from lintel.infrastructure.event_bus.subscriptions import (
    catch_up_subscribe,
    filtered_subscribe,
    live_subscribe,
)
from lintel.infrastructure.event_store.in_memory import InMemoryEventStore


def _make_event(event_type: str = "TestEvent") -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        schema_version=1,
        occurred_at=datetime.now(UTC),
        actor_type=ActorType.SYSTEM,
        actor_id="test",
        correlation_id=uuid4(),
        payload={},
    )


class _RecordingHandler:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def handle(self, event: EventEnvelope) -> None:
        self.events.append(event)


class TestCatchUpSubscribe:
    async def test_replays_historical_then_receives_live(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        # Store historical events
        historical = _make_event("TypeA")
        await store.append("stream-1", [historical])

        import asyncio

        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        sub_id = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        # Historical event was replayed
        assert len(handler.events) == 1
        assert handler.events[0].event_id == historical.event_id

        # Now publish a live event
        live = _make_event("TypeA")
        await store.append("stream-1", [live])
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2
        assert handler.events[1].event_id == live.event_id

        await bus.unsubscribe(sub_id)

    async def test_no_historical_events(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        handler = _RecordingHandler()
        await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        assert len(handler.events) == 0

    async def test_filters_by_event_type(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        await store.append("s1", [_make_event("TypeA"), _make_event("TypeB")])

        import asyncio

        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        assert len(handler.events) == 1
        assert handler.events[0].event_type == "TypeA"


class TestLiveSubscribe:
    async def test_receives_only_new_events(self) -> None:
        bus = InMemoryEventBus()

        handler = _RecordingHandler()
        sub_id = await live_subscribe(bus, frozenset({"TypeA"}), handler)

        event = _make_event("TypeA")
        await bus.publish(event)

        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_id == event.event_id

        await bus.unsubscribe(sub_id)


class TestFilteredSubscribe:
    async def test_requires_event_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()

        with pytest.raises(ValueError, match="at least one event type"):
            await filtered_subscribe(bus, frozenset(), handler)

    async def test_subscribes_to_specific_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        await filtered_subscribe(bus, frozenset({"TypeA", "TypeB"}), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeC"))

        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_type == "TypeA"
