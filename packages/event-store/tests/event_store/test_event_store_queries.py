"""Unit tests for EventStore query extensions (EVT-3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.event_store.in_memory import InMemoryEventStore


def _make_event(
    event_type: str = "TestEvent",
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        schema_version=1,
        occurred_at=occurred_at or datetime.now(UTC),
        actor_type=ActorType.SYSTEM,
        actor_id="test",
        correlation_id=uuid4(),
        payload={},
    )


class TestReadByEventType:
    async def test_returns_matching_events(self) -> None:
        store = InMemoryEventStore()
        e1 = _make_event("TypeA")
        e2 = _make_event("TypeB")
        e3 = _make_event("TypeA")
        await store.append("s1", [e1, e2, e3])

        result = await store.read_by_event_type("TypeA")
        assert len(result) == 2
        assert all(e.event_type == "TypeA" for e in result)

    async def test_returns_empty_for_no_match(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event("TypeA")])

        result = await store.read_by_event_type("TypeB")
        assert result == []

    async def test_respects_offset_and_limit(self) -> None:
        store = InMemoryEventStore()
        now = datetime.now(UTC)
        events = [_make_event("TypeA", occurred_at=now + timedelta(seconds=i)) for i in range(5)]
        await store.append("s1", events)

        result = await store.read_by_event_type("TypeA", from_position=1, limit=2)
        assert len(result) == 2

    async def test_across_multiple_streams(self) -> None:
        store = InMemoryEventStore()
        await store.append("s1", [_make_event("TypeA")])
        await store.append("s2", [_make_event("TypeA")])

        result = await store.read_by_event_type("TypeA")
        assert len(result) == 2


class TestReadByTimeRange:
    async def test_returns_events_in_range(self) -> None:
        store = InMemoryEventStore()
        now = datetime.now(UTC)
        old = _make_event("TypeA", occurred_at=now - timedelta(hours=2))
        mid = _make_event("TypeA", occurred_at=now - timedelta(hours=1))
        new = _make_event("TypeA", occurred_at=now)
        await store.append("s1", [old, mid, new])

        result = await store.read_by_time_range(
            now - timedelta(hours=1, minutes=30),
            now - timedelta(minutes=30),
        )
        assert len(result) == 1
        assert result[0].event_id == mid.event_id

    async def test_filters_by_event_types(self) -> None:
        store = InMemoryEventStore()
        now = datetime.now(UTC)
        e1 = _make_event("TypeA", occurred_at=now)
        e2 = _make_event("TypeB", occurred_at=now)
        await store.append("s1", [e1, e2])

        result = await store.read_by_time_range(
            now - timedelta(seconds=1),
            now + timedelta(seconds=1),
            event_types=frozenset({"TypeA"}),
        )
        assert len(result) == 1
        assert result[0].event_type == "TypeA"

    async def test_no_type_filter_returns_all(self) -> None:
        store = InMemoryEventStore()
        now = datetime.now(UTC)
        await store.append(
            "s1",
            [
                _make_event("TypeA", occurred_at=now),
                _make_event("TypeB", occurred_at=now),
            ],
        )

        result = await store.read_by_time_range(
            now - timedelta(seconds=1),
            now + timedelta(seconds=1),
        )
        assert len(result) == 2

    async def test_empty_range(self) -> None:
        store = InMemoryEventStore()
        now = datetime.now(UTC)
        await store.append("s1", [_make_event("TypeA", occurred_at=now)])

        result = await store.read_by_time_range(
            now + timedelta(hours=1),
            now + timedelta(hours=2),
        )
        assert result == []
