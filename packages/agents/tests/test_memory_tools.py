"""Tests for agent memory tools (schemas, dispatcher, helpers)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from lintel.agents.memory_tools import (
    MemoryToolDispatcher,
    is_memory_tool,
    memory_tool_schemas,
)
from lintel.memory.models import MemoryChunk, MemoryFact, MemoryType

_PROJECT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _make_fact(
    *,
    content: str = "Use pytest fixtures for DI",
    fact_type: str = "pattern",
    memory_type: MemoryType = MemoryType.LONG_TERM,
    source_workflow_id: UUID | None = None,
) -> MemoryFact:
    return MemoryFact(
        id=uuid4(),
        project_id=_PROJECT_ID,
        memory_type=memory_type,
        fact_type=fact_type,
        content=content,
        source_workflow_id=source_workflow_id,
    )


def _make_chunk(
    fact: MemoryFact | None = None,
    score: float = 0.88,
    rank: int = 1,
) -> MemoryChunk:
    return MemoryChunk(fact=fact or _make_fact(), score=score, rank=rank)


class TestMemoryToolSchemas:
    def test_returns_correct_schema_format(self) -> None:
        schemas = memory_tool_schemas()
        assert len(schemas) == 2

        names = {s["function"]["name"] for s in schemas}
        assert names == {"recall_memory", "store_memory"}

        for schema in schemas:
            assert schema["type"] == "function"
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]
            params = schema["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_recall_memory_schema_has_required_fields(self) -> None:
        schemas = memory_tool_schemas()
        recall = next(s for s in schemas if s["function"]["name"] == "recall_memory")
        assert set(recall["function"]["parameters"]["required"]) == {"query", "project_id"}

    def test_store_memory_schema_has_required_fields(self) -> None:
        schemas = memory_tool_schemas()
        store = next(s for s in schemas if s["function"]["name"] == "store_memory")
        assert set(store["function"]["parameters"]["required"]) == {
            "project_id",
            "content",
            "fact_type",
        }

    def test_exclude_filters_tools(self) -> None:
        schemas = memory_tool_schemas(exclude={"store_memory"})
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "recall_memory"

    def test_exclude_all_returns_empty(self) -> None:
        schemas = memory_tool_schemas(exclude={"recall_memory", "store_memory"})
        assert schemas == []


class TestIsMemoryTool:
    def test_recall_memory_is_memory_tool(self) -> None:
        assert is_memory_tool("recall_memory") is True

    def test_store_memory_is_memory_tool(self) -> None:
        assert is_memory_tool("store_memory") is True

    def test_unknown_tool_is_not_memory_tool(self) -> None:
        assert is_memory_tool("run_code") is False

    def test_empty_string_is_not_memory_tool(self) -> None:
        assert is_memory_tool("") is False

    def test_prefix_match_does_not_count(self) -> None:
        assert is_memory_tool("recall_memory_v2") is False


class TestMemoryToolDispatcher:
    @pytest.fixture()
    def mock_service(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def dispatcher(self, mock_service: AsyncMock) -> MemoryToolDispatcher:
        return MemoryToolDispatcher(mock_service)

    async def test_dispatch_recall_calls_service(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        chunks = [_make_chunk(score=0.91, rank=1)]
        mock_service.recall.return_value = chunks

        result = await dispatcher.dispatch(
            "recall_memory",
            {"query": "coding patterns", "project_id": str(_PROJECT_ID)},
        )

        mock_service.recall.assert_awaited_once()
        call_kwargs = mock_service.recall.call_args.kwargs
        assert call_kwargs["project_id"] == _PROJECT_ID
        assert call_kwargs["query"] == "coding patterns"
        assert "Relevant memories:" in result

    async def test_dispatch_recall_formats_output_concisely(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        fact = _make_fact(content="Always use type hints", fact_type="convention")
        chunks = [_make_chunk(fact=fact, score=0.95, rank=1)]
        mock_service.recall.return_value = chunks

        result = await dispatcher.dispatch(
            "recall_memory",
            {"query": "conventions", "project_id": str(_PROJECT_ID)},
        )

        assert "Relevant memories:" in result
        assert "[convention]" in result
        assert "Always use type hints" in result
        assert "0.95" in result
        # Should NOT contain raw JSON
        assert "{" not in result

    async def test_dispatch_recall_no_results(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        mock_service.recall.return_value = []

        result = await dispatcher.dispatch(
            "recall_memory",
            {"query": "nonexistent", "project_id": str(_PROJECT_ID)},
        )

        assert result == "No relevant memories found."

    async def test_dispatch_recall_with_workflow_source(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        wf_id = uuid4()
        fact = _make_fact(
            content="Learned from workflow",
            source_workflow_id=wf_id,
        )
        chunks = [_make_chunk(fact=fact, score=0.85, rank=1)]
        mock_service.recall.return_value = chunks

        result = await dispatcher.dispatch(
            "recall_memory",
            {"query": "workflow learnings", "project_id": str(_PROJECT_ID)},
        )

        assert "(from workflow)" in result

    async def test_dispatch_recall_with_memory_type_filter(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        mock_service.recall.return_value = []

        await dispatcher.dispatch(
            "recall_memory",
            {
                "query": "test",
                "project_id": str(_PROJECT_ID),
                "memory_type": "episodic",
            },
        )

        call_kwargs = mock_service.recall.call_args.kwargs
        assert call_kwargs["memory_type"] == MemoryType.EPISODIC

    async def test_dispatch_recall_all_memory_type(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        mock_service.recall.return_value = []

        await dispatcher.dispatch(
            "recall_memory",
            {
                "query": "test",
                "project_id": str(_PROJECT_ID),
                "memory_type": "all",
            },
        )

        call_kwargs = mock_service.recall.call_args.kwargs
        assert call_kwargs["memory_type"] is None

    async def test_dispatch_store_calls_service(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        fact = _make_fact(content="New pattern discovered")
        mock_service.store_memory.return_value = fact

        result = await dispatcher.dispatch(
            "store_memory",
            {
                "project_id": str(_PROJECT_ID),
                "content": "New pattern discovered",
                "fact_type": "pattern",
            },
        )

        mock_service.store_memory.assert_awaited_once()
        call_kwargs = mock_service.store_memory.call_args.kwargs
        assert call_kwargs["project_id"] == _PROJECT_ID
        assert call_kwargs["content"] == "New pattern discovered"
        assert call_kwargs["fact_type"] == "pattern"
        assert call_kwargs["memory_type"] == MemoryType.LONG_TERM
        assert "Memory stored:" in result

    async def test_dispatch_store_with_episodic_type(
        self, dispatcher: MemoryToolDispatcher, mock_service: AsyncMock
    ) -> None:
        fact = _make_fact(memory_type=MemoryType.EPISODIC)
        mock_service.store_memory.return_value = fact

        await dispatcher.dispatch(
            "store_memory",
            {
                "project_id": str(_PROJECT_ID),
                "content": "Episodic note",
                "fact_type": "issue",
                "memory_type": "episodic",
            },
        )

        call_kwargs = mock_service.store_memory.call_args.kwargs
        assert call_kwargs["memory_type"] == MemoryType.EPISODIC

    async def test_dispatch_unknown_tool_returns_error_string(
        self, dispatcher: MemoryToolDispatcher
    ) -> None:
        result = await dispatcher.dispatch("unknown_tool", {})

        assert "Unknown memory tool" in result
        assert "unknown_tool" in result

    def test_class_is_memory_tool(self) -> None:
        assert MemoryToolDispatcher.is_memory_tool("recall_memory") is True
        assert MemoryToolDispatcher.is_memory_tool("store_memory") is True
        assert MemoryToolDispatcher.is_memory_tool("other") is False

    def test_class_tool_schemas(self) -> None:
        schemas = MemoryToolDispatcher.tool_schemas()
        assert len(schemas) == 2
