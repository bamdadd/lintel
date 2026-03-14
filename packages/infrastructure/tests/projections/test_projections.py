"""Tests for projections."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.contracts.events import (
    AgentStepCompleted,
    AgentStepScheduled,
    AgentStepStarted,
    HumanApprovalGranted,
    ThreadMessageReceived,
    WorkflowAdvanced,
    WorkflowStarted,
)
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection


def _thread_ref() -> ThreadRef:
    return ThreadRef("W1", "C1", "t1")


class TestThreadStatusProjection:
    async def test_handles_expected_event_types(self) -> None:
        proj = ThreadStatusProjection()
        assert "ThreadMessageReceived" in proj.handled_event_types
        assert "WorkflowStarted" in proj.handled_event_types
        assert "HumanApprovalGranted" in proj.handled_event_types

    async def test_project_tracks_event_count(self) -> None:
        proj = ThreadStatusProjection()
        ref = _thread_ref()
        await proj.project(ThreadMessageReceived(thread_ref=ref))
        await proj.project(WorkflowStarted(thread_ref=ref))

        status = proj.get_status(ref.stream_id)
        assert status is not None
        assert status["event_count"] == 2

    async def test_project_updates_status(self) -> None:
        proj = ThreadStatusProjection()
        ref = _thread_ref()
        await proj.project(WorkflowStarted(thread_ref=ref))
        status = proj.get_status(ref.stream_id)
        assert status is not None
        assert status["status"] == "active"

    async def test_rebuild_clears_and_replays(self) -> None:
        proj = ThreadStatusProjection()
        ref = _thread_ref()
        await proj.project(ThreadMessageReceived(thread_ref=ref))
        assert proj.get_status(ref.stream_id)["event_count"] == 1  # type: ignore[index]

        events = [
            WorkflowStarted(thread_ref=ref),
            WorkflowAdvanced(thread_ref=ref),
            HumanApprovalGranted(thread_ref=ref),
        ]
        await proj.rebuild(events)
        status = proj.get_status(ref.stream_id)
        assert status is not None
        assert status["event_count"] == 3
        assert status["status"] == "approved"


class TestTaskBacklogProjection:
    async def test_handles_agent_events(self) -> None:
        proj = TaskBacklogProjection()
        assert "AgentStepScheduled" in proj.handled_event_types
        assert "AgentStepStarted" in proj.handled_event_types
        assert "AgentStepCompleted" in proj.handled_event_types

    async def test_tracks_task_lifecycle(self) -> None:
        proj = TaskBacklogProjection()
        ref = _thread_ref()
        from uuid import uuid4

        cid = uuid4()
        await proj.project(
            AgentStepScheduled(
                thread_ref=ref,
                correlation_id=cid,
                payload={"agent_role": "coder", "step_name": "coding"},
            )
        )
        tasks = proj.get_backlog()
        assert len(tasks) == 1
        assert tasks[0]["status"] == "scheduled"

        await proj.project(AgentStepStarted(thread_ref=ref, correlation_id=cid))
        assert proj.get_backlog()[0]["status"] == "in_progress"

        await proj.project(AgentStepCompleted(thread_ref=ref, correlation_id=cid))
        assert proj.get_backlog()[0]["status"] == "completed"

    async def test_get_pending_filters_completed(self) -> None:
        proj = TaskBacklogProjection()
        ref = _thread_ref()
        from uuid import uuid4

        cid1, cid2 = uuid4(), uuid4()
        await proj.project(AgentStepScheduled(thread_ref=ref, correlation_id=cid1))
        await proj.project(AgentStepCompleted(thread_ref=ref, correlation_id=cid2))

        pending = proj.get_pending()
        assert len(pending) == 1


class TestInMemoryProjectionEngine:
    async def test_dispatches_to_matching_projection(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = ThreadStatusProjection()
        await engine.register(proj)

        ref = _thread_ref()
        await engine.project(WorkflowStarted(thread_ref=ref))

        status = proj.get_status(ref.stream_id)
        assert status is not None
        assert status["status"] == "active"

    async def test_ignores_unhandled_events(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = ThreadStatusProjection()
        await engine.register(proj)

        ref = _thread_ref()
        await engine.project(AgentStepStarted(thread_ref=ref))

        assert proj.get_all() == []

    async def test_rebuild_reads_from_event_store(self) -> None:
        mock_store = AsyncMock()
        ref = _thread_ref()
        mock_store.read_stream.return_value = [
            WorkflowStarted(thread_ref=ref),
            WorkflowAdvanced(thread_ref=ref),
        ]
        engine = InMemoryProjectionEngine(event_store=mock_store)
        proj = ThreadStatusProjection()
        await engine.register(proj)

        await engine.rebuild_all(ref.stream_id)

        status = proj.get_status(ref.stream_id)
        assert status is not None
        assert status["event_count"] == 2
