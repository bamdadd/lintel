"""Integration test: workflow lifecycle with event store."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest

from lintel.contracts.events import (
    HumanApprovalGranted,
    ThreadMessageReceived,
    WorkflowAdvanced,
    WorkflowStarted,
)
from lintel.contracts.types import ActorType, ThreadRef, WorkflowPhase
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


async def test_workflow_lifecycle(event_store: PostgresEventStore) -> None:
    """Full lifecycle: message -> workflow start -> advance -> approval."""
    thread_ref = ThreadRef("W1", "C1", "wf.ts")
    corr_id = uuid4()

    events = [
        ThreadMessageReceived(
            actor_type=ActorType.HUMAN,
            actor_id="U123",
            thread_ref=thread_ref,
            correlation_id=corr_id,
            payload={"sanitized_text": "Fix the login bug", "sender_id": "U123"},
        ),
        WorkflowStarted(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            thread_ref=thread_ref,
            correlation_id=corr_id,
            payload={"workflow_type": "bug_fix"},
        ),
        WorkflowAdvanced(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            thread_ref=thread_ref,
            correlation_id=corr_id,
            payload={"phase": WorkflowPhase.IMPLEMENTING},
        ),
        HumanApprovalGranted(
            actor_type=ActorType.HUMAN,
            actor_id="U456",
            thread_ref=thread_ref,
            correlation_id=corr_id,
            payload={"gate_type": "pr_approval", "approver_id": "U456"},
        ),
    ]

    await event_store.append(thread_ref.stream_id, events)

    # Verify all events stored
    stored = await event_store.read_stream(thread_ref.stream_id)
    assert len(stored) == 4

    # Verify correlation query
    correlated = await event_store.read_by_correlation(corr_id)
    assert len(correlated) == 4

    # Verify projection reflects final state
    engine = InMemoryProjectionEngine(event_store)
    projection = ThreadStatusProjection()
    await engine.register(projection)
    await engine.rebuild_all(thread_ref.stream_id)

    status = projection.get_status(thread_ref.stream_id)
    assert status is not None
    assert status["status"] == "approved"
    assert status["event_count"] == 4
