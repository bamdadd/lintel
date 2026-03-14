"""Unit tests for InMemoryEventBus."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.event_bus.in_memory import InMemoryEventBus


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


class _RecordingHandler:
    """Test handler that records received events."""

    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def handle(self, event: EventEnvelope) -> None:
        self.events.append(event)


class _FailingHandler:
    """Test handler that always raises."""

    async def handle(self, event: EventEnvelope) -> None:
        msg = "handler failure"
        raise RuntimeError(msg)


class TestInMemoryEventBus:
    async def test_publish_delivers_to_subscriber(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        await bus.subscribe(frozenset({"TestEvent"}), handler)

        event = _make_event("TestEvent")
        await bus.publish(event)

        # Allow the delivery task to complete
        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_id == event.event_id

    async def test_publish_filters_by_event_type(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        await bus.subscribe(frozenset({"TypeA"}), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeB"))

        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler.events) == 1
        assert handler.events[0].event_type == "TypeA"

    async def test_empty_frozenset_receives_all_events(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        await bus.subscribe(frozenset(), handler)

        await bus.publish(_make_event("TypeA"))
        await bus.publish(_make_event("TypeB"))

        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler.events) == 2

    async def test_multiple_subscribers(self) -> None:
        bus = InMemoryEventBus()
        handler1 = _RecordingHandler()
        handler2 = _RecordingHandler()
        await bus.subscribe(frozenset({"TestEvent"}), handler1)
        await bus.subscribe(frozenset({"TestEvent"}), handler2)

        await bus.publish(_make_event("TestEvent"))

        import asyncio

        await asyncio.sleep(0.01)

        assert len(handler1.events) == 1
        assert len(handler2.events) == 1

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = InMemoryEventBus()
        handler = _RecordingHandler()
        sub_id = await bus.subscribe(frozenset({"TestEvent"}), handler)

        await bus.publish(_make_event("TestEvent"))
        import asyncio

        await asyncio.sleep(0.01)
        assert len(handler.events) == 1

        await bus.unsubscribe(sub_id)
        await bus.publish(_make_event("TestEvent"))
        await asyncio.sleep(0.01)
        assert len(handler.events) == 1  # no new events

    async def test_unsubscribe_unknown_id_is_noop(self) -> None:
        bus = InMemoryEventBus()
        await bus.unsubscribe("nonexistent")  # should not raise

    async def test_handler_error_does_not_block_other_subscribers(self) -> None:
        bus = InMemoryEventBus()
        failing = _FailingHandler()
        recording = _RecordingHandler()
        await bus.subscribe(frozenset({"TestEvent"}), failing)
        await bus.subscribe(frozenset({"TestEvent"}), recording)

        await bus.publish(_make_event("TestEvent"))

        import asyncio

        await asyncio.sleep(0.01)

        # Recording handler still receives the event despite failing handler
        assert len(recording.events) == 1

    async def test_subscription_count(self) -> None:
        bus = InMemoryEventBus()
        assert bus.subscription_count == 0
        sub1 = await bus.subscribe(frozenset({"A"}), _RecordingHandler())
        assert bus.subscription_count == 1
        sub2 = await bus.subscribe(frozenset({"B"}), _RecordingHandler())
        assert bus.subscription_count == 2
        await bus.unsubscribe(sub1)
        assert bus.subscription_count == 1
        await bus.unsubscribe(sub2)
        assert bus.subscription_count == 0

    async def test_publish_with_no_subscribers(self) -> None:
        bus = InMemoryEventBus()
        # Should not raise
        await bus.publish(_make_event("TestEvent"))
