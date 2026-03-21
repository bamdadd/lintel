"""Unit tests for read_all_from_position async generator on InMemoryEventStore."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.event_store.in_memory import InMemoryEventStore


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


class TestReadAllFromPosition:
    async def test_returns_all_events_from_position_zero(self) -> None:
        store = InMemoryEventStore()
        events = [_make_event() for _ in range(3)]
        await store.append("s1", events)

        result = [e async for e in store.read_all_from_position(0)]
        assert len(result) == 3

    async def test_returns_events_after_position(self) -> None:
        store = InMemoryEventStore()
        events = [_make_event() for _ in range(5)]
        await store.append("s1", events)

        # Position 3 means events with position > 3
        result = [e async for e in store.read_all_from_position(3)]
        assert len(result) == 2
        assert all(e.global_position is not None and e.global_position > 3 for e in result)

    async def test_returns_empty_when_no_events(self) -> None:
        store = InMemoryEventStore()
        result = [e async for e in store.read_all_from_position(0)]
        assert result == []

    async def test_returns_empty_when_position_beyond_all(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event()])
        result = [e async for e in store.read_all_from_position(100)]
        assert result == []

    async def test_events_ordered_by_global_position(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event()])
        await store.append("s2", [_make_event()])
        await store.append("s1", [_make_event()])

        result = [e async for e in store.read_all_from_position(0)]
        positions = [e.global_position for e in result]
        assert positions == sorted(positions)

    async def test_events_across_multiple_streams(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event(), _make_event()])
        await store.append("s2", [_make_event()])

        result = [e async for e in store.read_all_from_position(0)]
        assert len(result) == 3

    async def test_global_position_populated(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event()])
        result = [e async for e in store.read_all_from_position(0)]
        assert len(result) == 1
        assert result[0].global_position is not None
        assert result[0].global_position > 0

    async def test_monotonically_increasing_positions(self) -> None:
        store = InMemoryEventStore()
        for _ in range(5):
            await store.append("s1", [_make_event()])

        result = [e async for e in store.read_all_from_position(0)]
        positions = [e.global_position for e in result]
        for i in range(1, len(positions)):
            assert positions[i] is not None
            assert positions[i - 1] is not None
            assert positions[i] > positions[i - 1]
