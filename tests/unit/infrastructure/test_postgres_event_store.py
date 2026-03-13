"""Tests for PostgresEventStore (mocked asyncpg pool) and _row_to_event."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from lintel.contracts.events import (
    EventEnvelope,
    ThreadMessageReceived,
    WorkflowStarted,
)
from lintel.contracts.types import ActorType, ThreadRef
from lintel.infrastructure.event_store.postgres import (
    IdempotencyViolationError,
    OptimisticConcurrencyError,
    PostgresEventStore,
    _row_to_event,
)

# ---------------------------------------------------------------------------
# _row_to_event unit tests (no DB needed)
# ---------------------------------------------------------------------------


class TestRowToEvent:
    def test_basic_deserialization(self) -> None:
        eid = uuid4()
        cid = uuid4()
        now = datetime.now(UTC)
        row: dict[str, object] = {
            "event_id": eid,
            "event_type": "ThreadMessageReceived",
            "schema_version": 1,
            "occurred_at": now,
            "actor_type": "human",
            "actor_id": "user-1",
            "thread_ref": json.dumps({"workspace_id": "ws", "channel_id": "ch", "thread_ts": "ts"}),
            "correlation_id": cid,
            "causation_id": None,
            "payload": json.dumps({"text": "hello"}),
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert isinstance(event, ThreadMessageReceived)
        assert event.event_id == eid
        assert event.actor_type == ActorType.HUMAN
        assert event.thread_ref is not None
        assert event.thread_ref.workspace_id == "ws"
        assert event.payload == {"text": "hello"}

    def test_null_thread_ref(self) -> None:
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "WorkflowStarted",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "system",
            "actor_id": "",
            "thread_ref": None,
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": "{}",
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert isinstance(event, WorkflowStarted)
        assert event.thread_ref is None

    def test_dict_payload(self) -> None:
        """When payload comes as dict (asyncpg JSONB auto-decode)."""
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "EventEnvelope",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "agent",
            "actor_id": "bot-1",
            "thread_ref": None,
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": {"key": "value"},
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert event.payload == {"key": "value"}

    def test_dict_thread_ref(self) -> None:
        """When thread_ref comes as dict (asyncpg JSONB auto-decode)."""
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "ThreadMessageReceived",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "human",
            "actor_id": "u1",
            "thread_ref": {"workspace_id": "w", "channel_id": "c", "thread_ts": "t"},
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": "{}",
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert event.thread_ref is not None
        assert event.thread_ref.channel_id == "c"

    def test_unknown_event_type_returns_base_envelope(self) -> None:
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "SomeUnknownEvent",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "system",
            "actor_id": "",
            "thread_ref": None,
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": "{}",
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert type(event) is EventEnvelope

    def test_global_position_deserialized(self) -> None:
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "ThreadMessageReceived",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "system",
            "actor_id": "",
            "thread_ref": None,
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": "{}",
            "idempotency_key": None,
            "global_position": 42,
        }
        event = _row_to_event(row)
        assert event.global_position == 42

    def test_global_position_none_when_absent(self) -> None:
        """Rows without global_position (pre-migration) return None."""
        row: dict[str, object] = {
            "event_id": uuid4(),
            "event_type": "EventEnvelope",
            "schema_version": 1,
            "occurred_at": datetime.now(UTC),
            "actor_type": "system",
            "actor_id": "",
            "thread_ref": None,
            "correlation_id": uuid4(),
            "causation_id": None,
            "payload": "{}",
            "idempotency_key": None,
        }
        event = _row_to_event(row)
        assert event.global_position is None


# ---------------------------------------------------------------------------
# PostgresEventStore with mocked pool
# ---------------------------------------------------------------------------


class _AsyncCtx:
    """Minimal async context manager for mocking."""

    def __init__(self, value: object = None) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a mock asyncpg pool with context manager support."""
    conn = AsyncMock()
    # transaction() must return an async-context-manager directly (not a coroutine)
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    # acquire() must return an async-context-manager directly
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    return pool, conn


class TestPostgresEventStoreAppend:
    async def test_append_executes_insert(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchval.return_value = -1  # no existing events
        store = PostgresEventStore(pool)
        event = ThreadMessageReceived(
            thread_ref=ThreadRef("ws", "ch", "ts"),
            payload={"text": "hi"},
        )
        await store.append("stream-1", [event])
        assert conn.execute.called

    async def test_append_with_version_conflict_raises(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchval.return_value = 5  # current version is 5
        store = PostgresEventStore(pool)
        event = ThreadMessageReceived(payload={})
        with pytest.raises(OptimisticConcurrencyError):
            await store.append("stream-1", [event], expected_version=3)

    async def test_append_with_idempotency_violation(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchval.side_effect = [
            -1,  # max version (expected_version check skipped)
            None,  # prev_hash
            -1,  # base_version
            1,  # idempotency check returns existing
        ]
        store = PostgresEventStore(pool)
        event = ThreadMessageReceived(payload={}, idempotency_key="dup-key")
        with pytest.raises(IdempotencyViolationError):
            await store.append("stream-1", [event])


class TestPostgresEventStoreRead:
    async def test_read_stream(self) -> None:
        pool, conn = _mock_pool()
        now = datetime.now(UTC)
        conn.fetch.return_value = [
            {
                "event_id": uuid4(),
                "event_type": "ThreadMessageReceived",
                "schema_version": 1,
                "occurred_at": now,
                "actor_type": "human",
                "actor_id": "u1",
                "thread_ref": None,
                "correlation_id": uuid4(),
                "causation_id": None,
                "payload": "{}",
                "idempotency_key": None,
            }
        ]
        store = PostgresEventStore(pool)
        events = await store.read_stream("stream-1")
        assert len(events) == 1
        assert isinstance(events[0], ThreadMessageReceived)

    async def test_read_all(self) -> None:
        pool, conn = _mock_pool()
        conn.fetch.return_value = []
        store = PostgresEventStore(pool)
        events = await store.read_all(from_position=0, limit=10)
        assert events == []

    async def test_read_by_correlation(self) -> None:
        pool, conn = _mock_pool()
        cid = uuid4()
        conn.fetch.return_value = []
        store = PostgresEventStore(pool)
        events = await store.read_by_correlation(cid)
        assert events == []
        conn.fetch.assert_called_once()

    async def test_read_by_event_type(self) -> None:
        pool, conn = _mock_pool()
        now = datetime.now(UTC)
        eid = uuid4()
        conn.fetch.return_value = [
            {
                "event_id": eid,
                "event_type": "ThreadMessageReceived",
                "schema_version": 1,
                "occurred_at": now,
                "actor_type": "system",
                "actor_id": "sys",
                "thread_ref": None,
                "correlation_id": uuid4(),
                "causation_id": None,
                "payload": "{}",
                "idempotency_key": None,
            }
        ]
        store = PostgresEventStore(pool)
        events = await store.read_by_event_type("ThreadMessageReceived", from_position=0, limit=10)
        assert len(events) == 1
        assert isinstance(events[0], ThreadMessageReceived)
        # Verify the SQL uses global_position filtering
        call_args = conn.fetch.call_args
        assert "event_type" in call_args[0][0]
        assert "global_position" in call_args[0][0]

    async def test_read_by_time_range_with_types(self) -> None:
        pool, conn = _mock_pool()
        now = datetime.now(UTC)
        conn.fetch.return_value = [
            {
                "event_id": uuid4(),
                "event_type": "WorkflowStarted",
                "schema_version": 1,
                "occurred_at": now,
                "actor_type": "system",
                "actor_id": "sys",
                "thread_ref": None,
                "correlation_id": uuid4(),
                "causation_id": None,
                "payload": "{}",
                "idempotency_key": None,
            }
        ]
        store = PostgresEventStore(pool)
        from datetime import timedelta

        events = await store.read_by_time_range(
            now - timedelta(hours=1),
            now + timedelta(hours=1),
            event_types=frozenset({"WorkflowStarted"}),
        )
        assert len(events) == 1
        assert isinstance(events[0], WorkflowStarted)
        # Verify the SQL includes event_type filtering via ANY
        call_args = conn.fetch.call_args
        assert "ANY" in call_args[0][0]

    async def test_read_by_time_range_without_types(self) -> None:
        pool, conn = _mock_pool()
        conn.fetch.return_value = []
        store = PostgresEventStore(pool)
        from datetime import timedelta

        now = datetime.now(UTC)
        events = await store.read_by_time_range(
            now - timedelta(hours=1),
            now + timedelta(hours=1),
        )
        assert events == []
        # Verify the SQL does NOT include event_type filter
        call_args = conn.fetch.call_args
        assert "ANY" not in call_args[0][0]
