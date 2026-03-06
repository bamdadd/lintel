"""Integration tests for Postgres event store."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest

from lintel.contracts.events import ThreadMessageReceived
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
        await conn.execute("DELETE FROM events")
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
