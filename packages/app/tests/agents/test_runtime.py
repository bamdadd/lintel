"""Tests for the agent runtime."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from lintel.agents.runtime import AgentRuntime
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


def _make_mocks() -> tuple[AsyncMock, AsyncMock]:
    event_store = AsyncMock()
    event_store.append = AsyncMock()

    model_router = AsyncMock()
    model_router.select_model = AsyncMock(
        return_value=ModelPolicy("anthropic", "claude-sonnet-4-20250514", 8192, 0.0),
    )
    model_router.call_model = AsyncMock(
        return_value={
            "content": "Hello, world!",
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "model": "claude-sonnet-4-20250514",
        },
    )
    return event_store, model_router


class TestAgentRuntime:
    """Tests for agent step execution."""

    async def test_execute_step_returns_model_result(self) -> None:
        event_store, model_router = _make_mocks()
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        result = await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.PLANNER,
            step_name="planning",
            messages=[{"role": "user", "content": "Plan a feature"}],
        )

        assert result["content"] == "Hello, world!"
        assert result["usage"]["input_tokens"] == 10

    async def test_execute_step_emits_four_events(self) -> None:
        event_store, model_router = _make_mocks()
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="coding",
            messages=[{"role": "user", "content": "Write code"}],
        )

        # Should emit: StepStarted, ModelSelected, ModelCallCompleted, StepCompleted
        assert event_store.append.call_count == 4

    async def test_execute_step_calls_select_model(self) -> None:
        event_store, model_router = _make_mocks()
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.REVIEWER,
            step_name="review",
            messages=[{"role": "user", "content": "Review code"}],
        )

        model_router.select_model.assert_awaited_once_with(
            AgentRole.REVIEWER,
            "review",
        )

    async def test_execute_step_passes_tools_to_model(self) -> None:
        event_store, model_router = _make_mocks()
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")
        tools: list[dict[str, Any]] = [{"type": "function", "name": "test"}]

        await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="coding",
            messages=[{"role": "user", "content": "Write code"}],
            tools=tools,
        )

        call_args = model_router.call_model.call_args
        assert call_args[0][2] == tools

    async def test_execute_step_uses_provided_correlation_id(self) -> None:
        event_store, model_router = _make_mocks()
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")
        cid = uuid4()

        await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.PLANNER,
            step_name="planning",
            messages=[],
            correlation_id=cid,
        )

        # All 4 event appends should use the same correlation_id
        for call in event_store.append.call_args_list:
            event = call[0][1][0]
            assert event.correlation_id == cid

    async def test_execute_step_stream_accumulates_chunks(self) -> None:
        event_store, model_router = _make_mocks()

        async def fake_stream(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            for chunk in ["Hello", ", ", "world!"]:
                yield chunk

        model_router.stream_model = fake_stream
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        result = await runtime.execute_step_stream(
            thread_ref=thread_ref,
            agent_role=AgentRole.PLANNER,
            step_name="planning",
            messages=[{"role": "user", "content": "Plan"}],
        )

        assert result["content"] == "Hello, world!"

    async def test_execute_step_stream_calls_on_chunk(self) -> None:
        event_store, model_router = _make_mocks()
        chunks_received: list[str] = []

        async def fake_stream(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            for chunk in ["line1\n", "line2\n"]:
                yield chunk

        model_router.stream_model = fake_stream
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        async def on_chunk(chunk: str) -> None:
            chunks_received.append(chunk)

        await runtime.execute_step_stream(
            thread_ref=thread_ref,
            agent_role=AgentRole.RESEARCHER,
            step_name="research",
            messages=[{"role": "user", "content": "Research"}],
            on_chunk=on_chunk,
        )

        assert chunks_received == ["line1\n", "line2\n"]

    async def test_execute_step_stream_emits_events(self) -> None:
        event_store, model_router = _make_mocks()

        async def fake_stream(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            yield "done"

        model_router.stream_model = fake_stream
        runtime = AgentRuntime(event_store, model_router)
        thread_ref = ThreadRef("W1", "C1", "t1")

        await runtime.execute_step_stream(
            thread_ref=thread_ref,
            agent_role=AgentRole.PLANNER,
            step_name="plan",
            messages=[],
        )

        # Should emit: StepStarted, ModelSelected, StepCompleted (3 events, no ModelCallCompleted)
        assert event_store.append.call_count == 3
