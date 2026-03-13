"""Integration tests for Postgres event store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest

from lintel.contracts.events import ThreadMessageReceived, WorkflowStarted
from lintel.contracts.types import ActorType, ThreadRef
from lintel.infrastructure.event_store.postgres import (
    IdempotencyViolationError,
    OptimisticConcurrencyError,
    PostgresEventStore,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def event_store(postgres_url: str) -> AsyncGenerator[PostgresEventStore]:
    pool = await asyncpg.create_pool(postgres_url)
    assert pool is not None
    async with pool.acquire() as conn:
        with open("migrations/001_create_event_store.sql") as f:
            await conn.execute(f.read())
        with open("migrations/006_add_global_position.sql") as f:
            await conn.execute(f.read())
        await conn.execute("DELETE FROM events")
        # Reset the global_position sequence so tests get predictable positions
        await conn.execute("ALTER SEQUENCE events_global_position_seq RESTART WITH 1")
    store = PostgresEventStore(pool)
    yield store
    await pool.close()


async def test_append_and_read_stream(event_store: PostgresEventStore) -> None:
    thread_ref = ThreadRef("W1", "C1", "1234.5678")
    event = ThreadMessageReceived(
        actor_type=ActorType.HUMAN,
        actor_id="U123",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={
            "sanitized_text": "Hello world",
            "sender_id": "U123",
        },
    )

    await event_store.append(thread_ref.stream_id, [event])
    events = await event_store.read_stream(thread_ref.stream_id)

    assert len(events) == 1
    assert events[0].event_type == "ThreadMessageReceived"
    assert events[0].payload["sanitized_text"] == "Hello world"


async def test_optimistic_concurrency(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "test"},
    )

    await event_store.append(stream_id, [event], expected_version=-1)

    with pytest.raises(OptimisticConcurrencyError):
        event2 = ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": "test2"},
        )
        await event_store.append(stream_id, [event2], expected_version=-1)


async def test_hash_chaining(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(3)
    ]

    await event_store.append(stream_id, events)
    stored = await event_store.read_stream(stream_id)
    assert len(stored) == 3


async def test_read_by_correlation(event_store: PostgresEventStore) -> None:
    corr_id = uuid4()
    stream_id = f"test:{uuid4()}"
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=corr_id,
        payload={"sanitized_text": "correlated"},
    )

    await event_store.append(stream_id, [event])
    results = await event_store.read_by_correlation(corr_id)
    assert len(results) == 1
    assert results[0].correlation_id == corr_id


async def test_read_all(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "read_all"},
    )

    await event_store.append(stream_id, [event])
    all_events = await event_store.read_all()
    assert len(all_events) >= 1


async def test_hash_chain_integrity(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(3)
    ]
    await event_store.append(stream_id, events)

    async with event_store._pool.acquire() as conn:  # type: ignore[no-untyped-call]
        rows = await conn.fetch(
            "SELECT payload_hash, prev_hash FROM events "
            "WHERE stream_id = $1 ORDER BY stream_version",
            stream_id,
        )
    assert rows[0]["prev_hash"] is None
    assert rows[1]["prev_hash"] == rows[0]["payload_hash"]
    assert rows[2]["prev_hash"] == rows[1]["payload_hash"]


async def test_read_stream_from_version(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(5)
    ]
    await event_store.append(stream_id, events)

    result = await event_store.read_stream(stream_id, from_version=3)
    assert len(result) == 2
    assert result[0].payload["sanitized_text"] == "msg 3"
    assert result[1].payload["sanitized_text"] == "msg 4"


async def test_read_all_with_offset_and_limit(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(5)
    ]
    await event_store.append(stream_id, events)

    result = await event_store.read_all(from_position=0, limit=2)
    assert len(result) == 2


async def test_thread_ref_round_trip(event_store: PostgresEventStore) -> None:
    thread_ref = ThreadRef("W1", "C1", "99.99")
    event = ThreadMessageReceived(
        actor_type=ActorType.HUMAN,
        actor_id="U1",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={"sanitized_text": "ref test"},
    )
    await event_store.append(thread_ref.stream_id, [event])
    stored = await event_store.read_stream(thread_ref.stream_id)
    assert stored[0].thread_ref is not None
    assert stored[0].thread_ref.workspace_id == "W1"
    assert stored[0].thread_ref.channel_id == "C1"
    assert stored[0].thread_ref.thread_ts == "99.99"
    assert stored[0].thread_ref.stream_id == "thread:W1:C1:99.99"


async def test_causation_id_persisted(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    cause_id = uuid4()
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        causation_id=cause_id,
        payload={"sanitized_text": "caused"},
    )
    await event_store.append(stream_id, [event])
    stored = await event_store.read_stream(stream_id)
    assert stored[0].causation_id == cause_id


async def test_idempotency(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    key = str(uuid4())
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "idempotent"},
        idempotency_key=key,
    )

    await event_store.append(stream_id, [event])
    with pytest.raises(IdempotencyViolationError):
        event2 = ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": "idempotent2"},
            idempotency_key=key,
        )
        await event_store.append(stream_id, [event2])


# ---------------------------------------------------------------------------
# EVT-3.1: read_by_event_type
# ---------------------------------------------------------------------------


async def test_read_by_event_type(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    msg = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "typed"},
    )
    wf = WorkflowStarted(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"workflow": "test"},
    )
    await event_store.append(stream_id, [msg, wf])

    results = await event_store.read_by_event_type("ThreadMessageReceived")
    assert len(results) >= 1
    assert all(e.event_type == "ThreadMessageReceived" for e in results)


async def test_read_by_event_type_with_limit(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(5)
    ]
    await event_store.append(stream_id, events)

    results = await event_store.read_by_event_type("ThreadMessageReceived", limit=3)
    assert len(results) == 3


async def test_read_by_event_type_from_position(event_store: PostgresEventStore) -> None:
    """from_position filters by global_position, not by offset."""
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(5)
    ]
    await event_store.append(stream_id, events)

    # Get all events to find their global_positions
    all_events = await event_store.read_by_event_type("ThreadMessageReceived")
    assert len(all_events) >= 5
    # Each event should have a global_position
    for e in all_events:
        assert e.global_position is not None

    # Read from a position midway through
    mid_pos = all_events[2].global_position
    assert mid_pos is not None
    from_mid = await event_store.read_by_event_type("ThreadMessageReceived", from_position=mid_pos)
    assert len(from_mid) >= 3
    assert all(
        e.global_position is not None and e.global_position >= mid_pos for e in from_mid
    )


# ---------------------------------------------------------------------------
# EVT-3.2: read_by_time_range
# ---------------------------------------------------------------------------


async def test_read_by_time_range(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    now = datetime.now(UTC)
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "time-range"},
    )
    await event_store.append(stream_id, [event])

    results = await event_store.read_by_time_range(
        from_time=now - timedelta(seconds=10),
        to_time=now + timedelta(seconds=10),
    )
    assert len(results) >= 1


async def test_read_by_time_range_with_event_types(event_store: PostgresEventStore) -> None:
    stream_id = f"test:{uuid4()}"
    now = datetime.now(UTC)
    msg = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "typed-range"},
    )
    wf = WorkflowStarted(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"workflow": "test"},
    )
    await event_store.append(stream_id, [msg, wf])

    results = await event_store.read_by_time_range(
        from_time=now - timedelta(seconds=10),
        to_time=now + timedelta(seconds=10),
        event_types=frozenset({"ThreadMessageReceived"}),
    )
    assert len(results) >= 1
    assert all(e.event_type == "ThreadMessageReceived" for e in results)


async def test_read_by_time_range_empty_window(event_store: PostgresEventStore) -> None:
    far_past = datetime(2020, 1, 1, tzinfo=UTC)
    results = await event_store.read_by_time_range(
        from_time=far_past,
        to_time=far_past + timedelta(seconds=1),
    )
    assert results == []


# ---------------------------------------------------------------------------
# EVT-3.3: global_position
# ---------------------------------------------------------------------------


async def test_global_position_assigned(event_store: PostgresEventStore) -> None:
    """Every persisted event gets a monotonically increasing global_position."""
    stream_a = f"test:{uuid4()}"
    stream_b = f"test:{uuid4()}"

    e1 = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "a1"},
    )
    e2 = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "b1"},
    )
    e3 = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "a2"},
    )

    await event_store.append(stream_a, [e1])
    await event_store.append(stream_b, [e2])
    await event_store.append(stream_a, [e3], expected_version=0)

    all_events = await event_store.read_all()
    positions = [e.global_position for e in all_events]
    # All positions should be non-None
    assert all(p is not None for p in positions)
    # Positions should be strictly increasing
    for i in range(1, len(positions)):
        assert positions[i] > positions[i - 1]  # type: ignore[operator]


async def test_read_all_uses_global_position(event_store: PostgresEventStore) -> None:
    """read_all(from_position=N) returns events with global_position >= N."""
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(5)
    ]
    await event_store.append(stream_id, events)

    all_events = await event_store.read_all()
    assert len(all_events) >= 5
    mid_pos = all_events[2].global_position
    assert mid_pos is not None

    from_mid = await event_store.read_all(from_position=mid_pos)
    assert all(
        e.global_position is not None and e.global_position >= mid_pos for e in from_mid
    )
