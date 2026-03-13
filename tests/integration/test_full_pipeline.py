"""Integration test: message ingestion through event store and projection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest
from lintel.contracts.events import ThreadMessageReceived, WorkflowStarted
from lintel.contracts.types import ActorType, ThreadRef
from lintel.infrastructure.event_store.postgres import PostgresEventStore
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection

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


async def test_message_ingestion_pipeline(event_store: PostgresEventStore) -> None:
    """Full pipeline: raw message -> event store -> projection."""
    thread_ref = ThreadRef("W1", "C1", "test.ts")

    # Create and store a message event
    msg_event = ThreadMessageReceived(
        actor_type=ActorType.HUMAN,
        actor_id="U123",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={"sanitized_text": "Hello world", "sender_id": "U123"},
    )
    await event_store.append(thread_ref.stream_id, [msg_event])

    # Create and store a workflow event
    wf_event = WorkflowStarted(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={"workflow_type": "code_review"},
    )
    await event_store.append(thread_ref.stream_id, [wf_event], expected_version=0)

    # Verify events stored
    stored = await event_store.read_stream(thread_ref.stream_id)
    assert len(stored) == 2
    assert stored[0].event_type == "ThreadMessageReceived"
    assert stored[1].event_type == "WorkflowStarted"

    # Verify projection
    engine = InMemoryProjectionEngine(event_store)
    projection = ThreadStatusProjection()
    await engine.register(projection)
    await engine.rebuild_all(thread_ref.stream_id)

    status = projection.get_status(thread_ref.stream_id)
    assert status is not None
    assert status["status"] == "active"
    assert status["event_count"] == 2
