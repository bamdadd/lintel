"""Tests for InMemoryProjectionEngine, TaskBacklogProjection, ThreadStatusProjection."""

from __future__ import annotations

from uuid import uuid4

import pytest

from lintel.contracts.events import (
    AgentStepCompleted,
    AgentStepScheduled,
    AgentStepStarted,
    EventEnvelope,
    HumanApprovalGranted,
    HumanApprovalRejected,
    ThreadMessageReceived,
    WorkflowAdvanced,
    WorkflowStarted,
)
from lintel.contracts.types import ThreadRef
from lintel.projections.engine import InMemoryProjectionEngine
from lintel.projections.task_backlog import TaskBacklogProjection
from lintel.projections.thread_status import ThreadStatusProjection


def _make_event(
    event_type: str,
    thread_ref: ThreadRef | None = None,
    **payload: object,
) -> EventEnvelope:
    cls_map = {
        "AgentStepScheduled": AgentStepScheduled,
        "AgentStepStarted": AgentStepStarted,
        "AgentStepCompleted": AgentStepCompleted,
        "ThreadMessageReceived": ThreadMessageReceived,
        "WorkflowStarted": WorkflowStarted,
        "WorkflowAdvanced": WorkflowAdvanced,
        "HumanApprovalGranted": HumanApprovalGranted,
        "HumanApprovalRejected": HumanApprovalRejected,
    }
    cls = cls_map[event_type]
    return cls(
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload=dict(payload),
    )


THREAD = ThreadRef("ws1", "ch1", "ts1")


class TestTaskBacklogProjection:
    def setup_method(self) -> None:
        self.proj = TaskBacklogProjection()

    async def test_scheduled_event_creates_task(self) -> None:
        event = _make_event("AgentStepScheduled", THREAD, agent_role="coder")
        await self.proj.project(event)
        backlog = self.proj.get_backlog()
        assert len(backlog) == 1
        assert backlog[0]["status"] == "scheduled"
        assert backlog[0]["agent_role"] == "coder"

    async def test_started_event_updates_status(self) -> None:
        cid = uuid4()
        e1 = AgentStepScheduled(correlation_id=cid, thread_ref=THREAD, payload={})
        e2 = AgentStepStarted(correlation_id=cid, thread_ref=THREAD, payload={})
        await self.proj.project(e1)
        await self.proj.project(e2)
        backlog = self.proj.get_backlog()
        assert len(backlog) == 1
        assert backlog[0]["status"] == "in_progress"

    async def test_completed_event_removes_from_pending(self) -> None:
        cid = uuid4()
        e1 = AgentStepScheduled(correlation_id=cid, thread_ref=THREAD, payload={})
        e2 = AgentStepCompleted(correlation_id=cid, thread_ref=THREAD, payload={})
        await self.proj.project(e1)
        await self.proj.project(e2)
        assert len(self.proj.get_pending()) == 0
        assert len(self.proj.get_backlog()) == 1

    async def test_rebuild_replays_events(self) -> None:
        cid = uuid4()
        events = [
            AgentStepScheduled(correlation_id=cid, thread_ref=THREAD, payload={}),
            AgentStepStarted(correlation_id=cid, thread_ref=THREAD, payload={}),
        ]
        await self.proj.rebuild(events)
        assert len(self.proj.get_backlog()) == 1
        assert self.proj.get_backlog()[0]["status"] == "in_progress"

    async def test_rebuild_clears_previous_state(self) -> None:
        event = _make_event("AgentStepScheduled", THREAD)
        await self.proj.project(event)
        assert len(self.proj.get_backlog()) == 1
        await self.proj.rebuild([])
        assert len(self.proj.get_backlog()) == 0

    def test_handled_event_types(self) -> None:
        types = self.proj.handled_event_types
        assert "AgentStepScheduled" in types
        assert "AgentStepStarted" in types
        assert "AgentStepCompleted" in types

    async def test_step_name_extracted_from_payload(self) -> None:
        event = _make_event("AgentStepScheduled", THREAD, step_name="plan")
        await self.proj.project(event)
        assert self.proj.get_backlog()[0]["step_name"] == "plan"


class TestThreadStatusProjection:
    def setup_method(self) -> None:
        self.proj = ThreadStatusProjection()

    async def test_message_received_creates_thread(self) -> None:
        event = _make_event("ThreadMessageReceived", THREAD)
        await self.proj.project(event)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["event_count"] == 1

    async def test_workflow_started_sets_active(self) -> None:
        event = _make_event("WorkflowStarted", THREAD)
        await self.proj.project(event)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["status"] == "active"

    async def test_approval_granted_sets_approved(self) -> None:
        event = _make_event("HumanApprovalGranted", THREAD)
        await self.proj.project(event)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["status"] == "approved"

    async def test_approval_rejected_sets_rejected(self) -> None:
        event = _make_event("HumanApprovalRejected", THREAD)
        await self.proj.project(event)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["status"] == "rejected"

    async def test_event_count_increments(self) -> None:
        e1 = _make_event("ThreadMessageReceived", THREAD)
        e2 = _make_event("WorkflowStarted", THREAD)
        await self.proj.project(e1)
        await self.proj.project(e2)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["event_count"] == 2

    async def test_get_all_returns_all_threads(self) -> None:
        t1 = ThreadRef("ws1", "ch1", "ts1")
        t2 = ThreadRef("ws1", "ch2", "ts2")
        await self.proj.project(_make_event("WorkflowStarted", t1))
        await self.proj.project(_make_event("WorkflowStarted", t2))
        assert len(self.proj.get_all()) == 2

    async def test_get_status_unknown_thread_returns_none(self) -> None:
        assert self.proj.get_status("nonexistent") is None

    async def test_rebuild(self) -> None:
        events = [
            _make_event("ThreadMessageReceived", THREAD),
            _make_event("WorkflowStarted", THREAD),
        ]
        await self.proj.rebuild(events)
        status = self.proj.get_status(str(THREAD))
        assert status is not None
        assert status["status"] == "active"
        assert status["event_count"] == 2

    def test_handled_event_types(self) -> None:
        types = self.proj.handled_event_types
        assert "WorkflowStarted" in types
        assert "HumanApprovalGranted" in types
        assert "ThreadMessageReceived" in types


class TestProjectionEngine:
    async def test_register_and_project(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = TaskBacklogProjection()
        await engine.register(proj)
        event = _make_event("AgentStepScheduled", THREAD)
        await engine.project(event)
        assert len(proj.get_backlog()) == 1

    async def test_unhandled_event_ignored(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = TaskBacklogProjection()
        await engine.register(proj)
        event = _make_event("WorkflowStarted", THREAD)
        await engine.project(event)
        assert len(proj.get_backlog()) == 0

    async def test_multiple_projections(self) -> None:
        engine = InMemoryProjectionEngine()
        backlog = TaskBacklogProjection()
        status = ThreadStatusProjection()
        await engine.register(backlog)
        await engine.register(status)

        await engine.project(_make_event("AgentStepScheduled", THREAD))
        await engine.project(_make_event("WorkflowStarted", THREAD))

        assert len(backlog.get_backlog()) == 1
        assert status.get_status(str(THREAD)) is not None

    async def test_reset_all(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = TaskBacklogProjection()
        await engine.register(proj)
        await engine.project(_make_event("AgentStepScheduled", THREAD))
        assert len(proj.get_backlog()) == 1
        await engine.reset_all()
        assert len(proj.get_backlog()) == 0

    async def test_rebuild_all_requires_event_store(self) -> None:
        engine = InMemoryProjectionEngine(event_store=None)
        with pytest.raises(RuntimeError, match="EventStore required"):
            await engine.rebuild_all("stream-1")

    async def test_rebuild_all_with_event_store(self) -> None:
        from lintel.event_store.in_memory import InMemoryEventStore

        store = InMemoryEventStore()
        engine = InMemoryProjectionEngine(event_store=store)
        proj = TaskBacklogProjection()
        await engine.register(proj)

        event = _make_event("AgentStepScheduled", THREAD)
        await store.append("stream-1", [event])

        await engine.rebuild_all("stream-1")
        assert len(proj.get_backlog()) == 1
