"""Tests for WorkQueueEntry and related contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
import pytest


class TestWorkQueueStatus:
    def test_status_is_str_enum(self) -> None:
        from lintel.contracts.work_queue import WorkQueueStatus

        assert isinstance(WorkQueueStatus.PENDING, str)

    def test_status_values(self) -> None:
        from lintel.contracts.work_queue import WorkQueueStatus

        assert WorkQueueStatus.PENDING == "pending"
        assert WorkQueueStatus.RUNNING == "running"
        assert WorkQueueStatus.DONE == "done"
        assert WorkQueueStatus.FAILED == "failed"


class TestWorkQueueEntry:
    def test_create_minimal(self) -> None:
        from lintel.contracts.work_queue import WorkQueueEntry, WorkQueueStatus

        entry = WorkQueueEntry(
            id=uuid4(),
            agent_id="agent-1",
            run_id=uuid4(),
            status=WorkQueueStatus.PENDING,
            created_at=datetime.now(tz=UTC),
        )
        assert entry.agent_id == "agent-1"
        assert entry.status == WorkQueueStatus.PENDING
        assert entry.priority == 0
        assert entry.pipeline_id is None
        assert entry.payload == {}
        assert entry.started_at is None
        assert entry.completed_at is None

    def test_create_full(self) -> None:
        from lintel.contracts.work_queue import WorkQueueEntry, WorkQueueStatus

        now = datetime.now(tz=UTC)
        entry = WorkQueueEntry(
            id=uuid4(),
            agent_id="agent-2",
            run_id=uuid4(),
            pipeline_id=uuid4(),
            priority=5,
            status=WorkQueueStatus.RUNNING,
            payload={"key": "value"},
            created_at=now,
            started_at=now,
            completed_at=None,
        )
        assert entry.priority == 5
        assert entry.payload == {"key": "value"}
        assert entry.started_at == now

    def test_is_frozen(self) -> None:
        from lintel.contracts.work_queue import WorkQueueEntry, WorkQueueStatus

        entry = WorkQueueEntry(
            id=uuid4(),
            agent_id="agent-1",
            run_id=uuid4(),
            status=WorkQueueStatus.PENDING,
            created_at=datetime.now(tz=UTC),
        )
        with pytest.raises((ValidationError, TypeError)):
            entry.agent_id = "other"  # type: ignore[misc]

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            from lintel.contracts.work_queue import WorkQueueEntry

            WorkQueueEntry(
                id=uuid4(),
                agent_id="agent-1",
                run_id=uuid4(),
                status="invalid",  # type: ignore[arg-type]
                created_at=datetime.now(tz=UTC),
            )


class TestConcurrencyState:
    def test_create(self) -> None:
        from lintel.contracts.concurrency import ConcurrencyState

        state = ConcurrencyState(active_slots=2, max_slots=5, queue_depth=3)
        assert state.active_slots == 2
        assert state.max_slots == 5
        assert state.queue_depth == 3

    def test_is_frozen(self) -> None:
        from lintel.contracts.concurrency import ConcurrencyState

        state = ConcurrencyState(active_slots=1, max_slots=5, queue_depth=0)
        with pytest.raises((ValidationError, TypeError)):
            state.active_slots = 2  # type: ignore[misc]


class TestSlotAcquiredEvent:
    def test_create(self) -> None:
        from lintel.contracts.concurrency import SlotAcquiredEvent

        now = datetime.now(tz=UTC)
        event = SlotAcquiredEvent(agent_id="agent-1", run_id=uuid4(), acquired_at=now)
        assert event.agent_id == "agent-1"
        assert event.acquired_at == now

    def test_is_frozen(self) -> None:
        from lintel.contracts.concurrency import SlotAcquiredEvent

        event = SlotAcquiredEvent(
            agent_id="agent-1", run_id=uuid4(), acquired_at=datetime.now(tz=UTC)
        )
        with pytest.raises((ValidationError, TypeError)):
            event.agent_id = "other"  # type: ignore[misc]


class TestSlotReleasedEvent:
    def test_create(self) -> None:
        from lintel.contracts.concurrency import SlotReleasedEvent

        now = datetime.now(tz=UTC)
        event = SlotReleasedEvent(
            agent_id="agent-1", run_id=uuid4(), released_at=now, outcome="done"
        )
        assert event.outcome == "done"

    def test_is_frozen(self) -> None:
        from lintel.contracts.concurrency import SlotReleasedEvent

        event = SlotReleasedEvent(
            agent_id="a", run_id=uuid4(), released_at=datetime.now(tz=UTC), outcome="done"
        )
        with pytest.raises((ValidationError, TypeError)):
            event.outcome = "failed"  # type: ignore[misc]


class TestAgentQueuedEvent:
    def test_create(self) -> None:
        from lintel.contracts.work_queue import AgentQueuedEvent

        now = datetime.now(tz=UTC)
        event = AgentQueuedEvent(agent_id="agent-1", run_id=uuid4(), queued_at=now, priority=3)
        assert event.priority == 3
        assert event.queued_at == now

    def test_default_priority(self) -> None:
        from lintel.contracts.work_queue import AgentQueuedEvent

        event = AgentQueuedEvent(agent_id="agent-1", run_id=uuid4(), queued_at=datetime.now(tz=UTC))
        assert event.priority == 0

    def test_is_frozen(self) -> None:
        from lintel.contracts.work_queue import AgentQueuedEvent

        event = AgentQueuedEvent(agent_id="a", run_id=uuid4(), queued_at=datetime.now(tz=UTC))
        with pytest.raises((ValidationError, TypeError)):
            event.agent_id = "b"  # type: ignore[misc]


class TestContractsExports:
    def test_work_queue_exports(self) -> None:
        from lintel.contracts import (
            AgentQueuedEvent,
            WorkQueueEntry,
            WorkQueueStatus,
        )

        assert WorkQueueEntry is not None
        assert WorkQueueStatus is not None
        assert AgentQueuedEvent is not None

    def test_concurrency_exports(self) -> None:
        from lintel.contracts import (
            ConcurrencyState,
            SlotAcquiredEvent,
            SlotReleasedEvent,
        )

        assert ConcurrencyState is not None
        assert SlotAcquiredEvent is not None
        assert SlotReleasedEvent is not None
