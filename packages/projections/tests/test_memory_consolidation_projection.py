"""Tests for the memory consolidation projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from lintel.projections.memory_consolidation import MemoryConsolidationProjection

_PROJECT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_WORKFLOW_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@dataclass(frozen=True)
class FakeEvent:
    """Minimal EventEnvelope stand-in for testing."""

    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@pytest.fixture()
def mock_memory_service() -> AsyncMock:
    service = AsyncMock()
    service.consolidate_from_workflow.return_value = []
    return service


@pytest.fixture()
def projection(mock_memory_service: AsyncMock) -> MemoryConsolidationProjection:
    return MemoryConsolidationProjection(mock_memory_service)


class TestProjectionMetadata:
    def test_name(self, projection: MemoryConsolidationProjection) -> None:
        assert projection.name == "memory_consolidation"

    def test_handled_event_types(self, projection: MemoryConsolidationProjection) -> None:
        types = projection.handled_event_types
        assert "PipelineRunCompleted" in types
        assert isinstance(types, set)


class TestProject:
    async def test_valid_event_calls_consolidate(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "workflow_id": str(_WORKFLOW_ID),
                "project_id": str(_PROJECT_ID),
                "summary": "Implemented feature X with tests",
            },
        )
        mock_memory_service.consolidate_from_workflow.return_value = []

        await projection.project(event)

        mock_memory_service.consolidate_from_workflow.assert_awaited_once_with(
            workflow_id=_WORKFLOW_ID,
            project_id=_PROJECT_ID,
            summary_text="Implemented feature X with tests",
        )

    async def test_uses_run_id_fallback(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "run_id": str(_WORKFLOW_ID),
                "project_id": str(_PROJECT_ID),
                "result": "Completed refactor",
            },
        )

        await projection.project(event)

        call_kwargs = mock_memory_service.consolidate_from_workflow.call_args.kwargs
        assert call_kwargs["workflow_id"] == _WORKFLOW_ID
        assert call_kwargs["summary_text"] == "Completed refactor"

    async def test_missing_project_id_skips(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "workflow_id": str(_WORKFLOW_ID),
                "summary": "some summary",
            },
        )

        await projection.project(event)

        mock_memory_service.consolidate_from_workflow.assert_not_awaited()

    async def test_missing_workflow_id_skips(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "project_id": str(_PROJECT_ID),
                "summary": "some summary",
            },
        )

        await projection.project(event)

        mock_memory_service.consolidate_from_workflow.assert_not_awaited()

    async def test_empty_summary_skips(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "workflow_id": str(_WORKFLOW_ID),
                "project_id": str(_PROJECT_ID),
                "summary": "",
            },
        )

        await projection.project(event)

        mock_memory_service.consolidate_from_workflow.assert_not_awaited()

    async def test_non_matching_event_type_ignored(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="SomethingElseHappened",
            payload={"workflow_id": str(_WORKFLOW_ID)},
        )

        await projection.project(event)

        mock_memory_service.consolidate_from_workflow.assert_not_awaited()

    async def test_memory_service_error_handled_gracefully(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "workflow_id": str(_WORKFLOW_ID),
                "project_id": str(_PROJECT_ID),
                "summary": "Feature implemented",
            },
        )
        mock_memory_service.consolidate_from_workflow.side_effect = RuntimeError("connection lost")

        # Should not raise -- the projection catches exceptions.
        await projection.project(event)

    async def test_updates_state_on_success(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        event = FakeEvent(
            event_type="PipelineRunCompleted",
            payload={
                "workflow_id": str(_WORKFLOW_ID),
                "project_id": str(_PROJECT_ID),
                "summary": "Completed task",
            },
        )
        mock_memory_service.consolidate_from_workflow.return_value = []

        await projection.project(event)

        state = projection.get_state()
        assert state["consolidated_count"] == 1
        assert state["last_workflow_id"] == str(_WORKFLOW_ID)


class TestRebuild:
    async def test_processes_multiple_events(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        events = [
            FakeEvent(
                event_type="PipelineRunCompleted",
                payload={
                    "workflow_id": str(uuid4()),
                    "project_id": str(_PROJECT_ID),
                    "summary": f"Task {i}",
                },
            )
            for i in range(3)
        ]

        await projection.rebuild(events)

        assert mock_memory_service.consolidate_from_workflow.await_count == 3
        assert projection.get_state()["consolidated_count"] == 3

    async def test_rebuild_resets_state(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        # Pre-seed state
        projection.restore_state({"consolidated_count": 10, "last_workflow_id": "old-id"})

        await projection.rebuild([])

        state = projection.get_state()
        assert state["consolidated_count"] == 0
        assert state["last_workflow_id"] is None

    async def test_rebuild_skips_non_handled_events(
        self,
        projection: MemoryConsolidationProjection,
        mock_memory_service: AsyncMock,
    ) -> None:
        events = [
            FakeEvent(event_type="SomeOtherEvent", payload={}),
            FakeEvent(
                event_type="PipelineRunCompleted",
                payload={
                    "workflow_id": str(_WORKFLOW_ID),
                    "project_id": str(_PROJECT_ID),
                    "summary": "Valid event",
                },
            ),
        ]

        await projection.rebuild(events)

        assert mock_memory_service.consolidate_from_workflow.await_count == 1


class TestState:
    def test_get_state_returns_copy(self, projection: MemoryConsolidationProjection) -> None:
        state = projection.get_state()
        state["consolidated_count"] = 999
        # Original should be unaffected
        assert projection.get_state()["consolidated_count"] == 0

    def test_restore_state(self, projection: MemoryConsolidationProjection) -> None:
        projection.restore_state({"consolidated_count": 5, "last_workflow_id": "abc"})
        state = projection.get_state()
        assert state["consolidated_count"] == 5
        assert state["last_workflow_id"] == "abc"

    def test_restore_state_makes_copy(self, projection: MemoryConsolidationProjection) -> None:
        original = {"consolidated_count": 3, "last_workflow_id": "xyz"}
        projection.restore_state(original)
        original["consolidated_count"] = 999
        assert projection.get_state()["consolidated_count"] == 3

    def test_initial_state(self, projection: MemoryConsolidationProjection) -> None:
        state = projection.get_state()
        assert state == {"consolidated_count": 0, "last_workflow_id": None}
