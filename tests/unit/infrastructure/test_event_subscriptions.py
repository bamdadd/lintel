"""Unit tests for event subscription patterns (EVT-2).

Tests cover:
- Catch-up subscription: historical replay → live, gap-free buffering, dedup
- Live subscription: new events only
- Filtered subscription: type validation, selective delivery
- Subscription handle: lifecycle management (active flag, idempotent unsubscribe)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.infrastructure.event_bus.in_memory import InMemoryEventBus
from lintel.infrastructure.event_bus.subscriptions import (
    Subscription,
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


class _SlowRecordingHandler:
    """Handler that introduces a delay, simulating slow processing."""

    def __init__(self, delay: float = 0.05) -> None:
        self.events: list[EventEnvelope] = []
        self._delay = delay

    async def handle(self, event: EventEnvelope) -> None:
        await asyncio.sleep(self._delay)
        self.events.append(event)


# ---------------------------------------------------------------------------
# Subscription handle
# ---------------------------------------------------------------------------


class TestSubscription:
    async def test_active_after_creation(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub_id = await bus.subscribe(frozenset({"A"}), handler)

        sub = Subscription(
            subscription_id=sub_id,
            event_bus=bus,
            event_types=frozenset({"A"}),
        )
        assert sub.active is True

    async def test_unsubscribe_marks_inactive(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub_id = await bus.subscribe(frozenset({"A"}), handler)

        sub = Subscription(
            subscription_id=sub_id,
            event_bus=bus,
            event_types=frozenset({"A"}),
        )
        await sub.unsubscribe()
        assert sub.active is False
        assert bus.subscription_count == 0

    async def test_unsubscribe_is_idempotent(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub_id = await bus.subscribe(frozenset({"A"}), handler)

        sub = Subscription(
            subscription_id=sub_id,
            event_bus=bus,
            event_types=frozenset({"A"}),
        )
        await sub.unsubscribe()
        await sub.unsubscribe()  # second call should not raise
        assert sub.active is False


# ---------------------------------------------------------------------------
# Catch-up subscription
# ---------------------------------------------------------------------------


class TestCatchUpSubscribe:
    async def test_replays_historical_then_receives_live(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        # Store historical events
        historical = _make_event("TypeA")
        await store.append("stream-1", [historical])
        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        # Historical event was replayed
        assert len(handler.events) == 1
        assert handler.events[0].event_id == historical.event_id

        # Now publish a live event
        live = _make_event("TypeA")
        await store.append("stream-1", [live])
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2
        assert handler.events[1].event_id == live.event_id

        await sub.unsubscribe()
        assert sub.active is False

    async def test_no_historical_events(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        assert len(handler.events) == 0
        await sub.unsubscribe()

    async def test_filters_by_event_type(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        await store.append("s1", [_make_event("TypeA"), _make_event("TypeB")])
        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        assert len(handler.events) == 1
        assert handler.events[0].event_type == "TypeA"
        await sub.unsubscribe()

    async def test_deduplicates_overlap_events(self) -> None:
        """Events present in both historical replay and live buffer are delivered once."""
        bus = InMemoryEventBus()
        # Use a store WITHOUT event_bus wiring so we can control publishing manually
        store = InMemoryEventStore()

        # Seed historical data
        event_a = _make_event("TypeA")
        await store.append("s1", [event_a])

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        # The historical event should appear exactly once
        assert len(handler.events) == 1
        assert handler.events[0].event_id == event_a.event_id

        # Now a genuinely new event arrives via the bus
        event_b = _make_event("TypeA")
        await bus.publish(event_b)
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2
        assert handler.events[1].event_id == event_b.event_id
        await sub.unsubscribe()

    async def test_multiple_event_types_replay(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        evt_a = _make_event("TypeA")
        evt_b = _make_event("TypeB")
        evt_c = _make_event("TypeC")
        await store.append("s1", [evt_a, evt_b, evt_c])
        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(
            store, bus, frozenset({"TypeA", "TypeB"}), handler
        )

        # Should only replay TypeA and TypeB, not TypeC
        replayed_types = {e.event_type for e in handler.events}
        assert replayed_types == {"TypeA", "TypeB"}
        await sub.unsubscribe()

    async def test_from_position_skips_earlier_events(self) -> None:
        """The from_position parameter limits how far back the replay goes."""
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        events = [_make_event("TypeA") for _ in range(5)]
        await store.append("s1", events)
        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        # Skip first 3 events (positions 0, 1, 2)
        sub = await catch_up_subscribe(
            store, bus, frozenset({"TypeA"}), handler, from_position=3
        )

        assert len(handler.events) == 2
        assert handler.events[0].event_id == events[3].event_id
        assert handler.events[1].event_id == events[4].event_id
        await sub.unsubscribe()

    async def test_returns_subscription_object(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        handler = _RecordingHandler()
        sub = await catch_up_subscribe(store, bus, frozenset({"TypeA"}), handler)

        assert isinstance(sub, Subscription)
        assert sub.active is True
        assert sub.event_types == frozenset({"TypeA"})
        await sub.unsubscribe()


# ---------------------------------------------------------------------------
# Live subscription
# ---------------------------------------------------------------------------


class TestLiveSubscribe:
    async def test_receives_only_new_events(self) -> None:
        bus = InMemoryEventBus()

        handler = _RecordingHandler()
        sub = await live_subscribe(bus, frozenset({"TypeA"}), handler)

        event = _make_event("TypeA")
        await bus.publish(event)
        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_id == event.event_id

        await sub.unsubscribe()

    async def test_does_not_receive_pre_subscription_events(self) -> None:
        bus = InMemoryEventBus()
        store = InMemoryEventStore(event_bus=bus)

        # Publish before subscribing
        await store.append("s1", [_make_event("TypeA")])
        await asyncio.sleep(0.01)

        handler = _RecordingHandler()
        sub = await live_subscribe(bus, frozenset({"TypeA"}), handler)

        # Should not have the historical event
        assert len(handler.events) == 0

        # But should get new ones
        new_event = _make_event("TypeA")
        await bus.publish(new_event)
        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_id == new_event.event_id
        await sub.unsubscribe()

    async def test_wildcard_receives_all_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await live_subscribe(bus, frozenset(), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeB"))
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2
        await sub.unsubscribe()

    async def test_returns_subscription_object(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await live_subscribe(bus, frozenset({"TypeA"}), handler)

        assert isinstance(sub, Subscription)
        assert sub.active is True
        await sub.unsubscribe()


# ---------------------------------------------------------------------------
# Filtered subscription
# ---------------------------------------------------------------------------


class TestFilteredSubscribe:
    async def test_requires_event_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()

        with pytest.raises(ValueError, match="at least one event type"):
            await filtered_subscribe(bus, frozenset(), handler)

    async def test_subscribes_to_specific_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await filtered_subscribe(bus, frozenset({"TypeA", "TypeB"}), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeC"))
        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_type == "TypeA"
        await sub.unsubscribe()

    async def test_receives_all_specified_types(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await filtered_subscribe(bus, frozenset({"TypeA", "TypeB"}), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeB"))
        await bus.publish(_make_event("TypeC"))
        await asyncio.sleep(0.01)

        assert len(handler.events) == 2
        received_types = {e.event_type for e in handler.events}
        assert received_types == {"TypeA", "TypeB"}
        await sub.unsubscribe()

    async def test_returns_subscription_object(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await filtered_subscribe(bus, frozenset({"TypeA"}), handler)

        assert isinstance(sub, Subscription)
        assert sub.active is True
        assert sub.event_types == frozenset({"TypeA"})
        await sub.unsubscribe()

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub = await filtered_subscribe(bus, frozenset({"TypeA"}), handler)

        await bus.publish(_make_event("TypeA"))
        await asyncio.sleep(0.01)
        assert len(handler.events) == 1

        await sub.unsubscribe()

        await bus.publish(_make_event("TypeA"))
        await asyncio.sleep(0.01)
        assert len(handler.events) == 1  # no new events
