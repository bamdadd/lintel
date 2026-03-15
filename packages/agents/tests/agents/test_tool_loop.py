"""Tests for the agentic tool loop in AgentRuntime."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.agents.runtime import AgentRuntime
from lintel.agents.sandbox_tools import SandboxToolDispatcher, sandbox_tool_schemas
from lintel.agents.types import AgentRole
from lintel.contracts.types import ThreadRef
from lintel.models.types import ModelPolicy


def _make_mocks() -> tuple[AsyncMock, AsyncMock]:
    event_store = AsyncMock()
    event_store.append = AsyncMock()

    model_router = AsyncMock()
    model_router.select_model = AsyncMock(
        return_value=ModelPolicy("anthropic", "claude-sonnet-4-20250514", 8192, 0.0),
    )
    return event_store, model_router


def _tool_call_response(
    tool_name: str,
    arguments: str,
    call_id: str = "call_1",
) -> dict[str, Any]:
    """Build a model response containing a tool call."""
    return {
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": arguments},
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "model": "claude-sonnet-4-20250514",
    }


def _final_response(content: str = "Done.") -> dict[str, Any]:
    return {
        "content": content,
        "usage": {"input_tokens": 15, "output_tokens": 10},
        "model": "claude-sonnet-4-20250514",
    }


class TestToolLoop:
    """Tests for tool call loop execution."""

    async def test_no_tool_calls_returns_immediately(self) -> None:
        event_store, model_router = _make_mocks()
        model_router.call_model = AsyncMock(return_value=_final_response("Hello"))

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Write code"}],
        )

        assert result["content"] == "Hello"
        assert result["tool_iterations"] == 0
        model_router.call_model.assert_awaited_once()

    async def test_tool_call_executes_and_loops(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()
        sandbox_manager.read_file = AsyncMock(return_value="file contents here")

        # First call returns tool_call, second returns final content
        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_read_file", '{"path": "/workspace/main.py"}'),
                _final_response("Implementation complete."),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Read main.py"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="sandbox-123",
        )

        assert result["content"] == "Implementation complete."
        assert result["tool_iterations"] == 1
        assert model_router.call_model.await_count == 2
        sandbox_manager.read_file.assert_awaited_once_with("sandbox-123", "/workspace/main.py")

    async def test_multiple_tool_iterations(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()
        sandbox_manager.read_file = AsyncMock(return_value="contents")
        sandbox_manager.write_file = AsyncMock()

        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_read_file", '{"path": "/workspace/app.py"}', "call_1"),
                _tool_call_response(
                    "sandbox_write_file",
                    '{"path": "/workspace/app.py", "content": "new code"}',
                    "call_2",
                ),
                _final_response("All done."),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Update app.py"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="sandbox-456",
        )

        assert result["content"] == "All done."
        assert result["tool_iterations"] == 2
        assert model_router.call_model.await_count == 3

    async def test_max_iterations_stops_loop(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()
        sandbox_manager.list_files = AsyncMock(return_value=["a.py", "b.py"])

        # Always return tool calls — should be stopped by max_iterations
        model_router.call_model = AsyncMock(
            return_value=_tool_call_response("sandbox_list_files", '{"path": "/workspace"}'),
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "List files"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="sandbox-789",
            max_iterations=3,
        )

        # 1 initial call + 3 iterations = 4 calls total
        assert model_router.call_model.await_count == 4
        assert result["tool_iterations"] == 3

    async def test_tool_results_appended_to_messages(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()
        sandbox_manager.read_file = AsyncMock(return_value="hello world")

        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_read_file", '{"path": "/workspace/x.txt"}'),
                _final_response("Got it."),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Read x.txt"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="sandbox-abc",
        )

        # Second call_model should have assistant + tool messages appended
        second_call_messages = model_router.call_model.call_args_list[1][0][1]
        assert len(second_call_messages) == 3  # user + assistant + tool
        assert second_call_messages[1]["role"] == "assistant"
        assert second_call_messages[2]["role"] == "tool"
        assert second_call_messages[2]["content"] == "hello world"

    async def test_aggregated_token_usage(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()
        sandbox_manager.read_file = AsyncMock(return_value="x")

        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_read_file", '{"path": "/workspace/f.py"}'),
                _final_response(),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Go"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="s1",
        )

        # 10+15 input, 5+10 output
        assert result["usage"]["input_tokens"] == 25
        assert result["usage"]["output_tokens"] == 15

    async def test_sandbox_not_available_returns_error_string(self) -> None:
        event_store, model_router = _make_mocks()

        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_read_file", '{"path": "/workspace/f.py"}'),
                _final_response("ok"),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Go"}],
            tools=sandbox_tool_schemas(),
            # No sandbox_manager or sandbox_id
        )

        # Should still complete (error string fed back to model)
        assert result["content"] == "ok"
        second_call_messages = model_router.call_model.call_args_list[1][0][1]
        tool_msg = second_call_messages[2]
        assert "Sandbox not available" in tool_msg["content"]

    async def test_execute_command_tool(self) -> None:
        event_store, model_router = _make_mocks()
        sandbox_manager = AsyncMock()

        from lintel.sandbox.types import SandboxResult

        sandbox_manager.execute = AsyncMock(
            return_value=SandboxResult(exit_code=0, stdout="test output\n", stderr="")
        )

        model_router.call_model = AsyncMock(
            side_effect=[
                _tool_call_response("sandbox_execute_command", '{"command": "python -m pytest"}'),
                _final_response("Tests passed."),
            ]
        )

        runtime = AgentRuntime(event_store, model_router)
        result = await runtime.execute_step(
            thread_ref=ThreadRef("W1", "C1", "t1"),
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "Run tests"}],
            tools=sandbox_tool_schemas(),
            sandbox_manager=sandbox_manager,
            sandbox_id="s1",
        )

        assert result["content"] == "Tests passed."
        sandbox_manager.execute.assert_awaited_once()


class TestSandboxToolSchemas:
    """Tests for sandbox tool schema definitions."""

    def test_schemas_are_valid_litellm_format(self) -> None:
        schemas = sandbox_tool_schemas()
        assert len(schemas) == 4
        for schema in schemas:
            assert schema["type"] == "function"
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["name"].startswith("sandbox_")

    def test_schema_names(self) -> None:
        names = [s["function"]["name"] for s in sandbox_tool_schemas()]
        assert names == [
            "sandbox_read_file",
            "sandbox_write_file",
            "sandbox_list_files",
            "sandbox_execute_command",
        ]


class TestSandboxToolDispatcher:
    """Tests for SandboxToolDispatcher class interface."""

    def test_is_sandbox_tool_classmethod(self) -> None:
        assert SandboxToolDispatcher.is_sandbox_tool("sandbox_read_file") is True
        assert SandboxToolDispatcher.is_sandbox_tool("sandbox_execute_command") is True
        assert SandboxToolDispatcher.is_sandbox_tool("some_other_tool") is False

    def test_tool_schemas_classmethod(self) -> None:
        schemas = SandboxToolDispatcher.tool_schemas()
        assert len(schemas) == 4
        names = [s["function"]["name"] for s in schemas]
        assert "sandbox_read_file" in names

    def test_tool_schemas_with_exclude(self) -> None:
        schemas = SandboxToolDispatcher.tool_schemas(exclude={"sandbox_list_files"})
        names = [s["function"]["name"] for s in schemas]
        assert "sandbox_list_files" not in names
        assert len(schemas) == 3

    async def test_dispatch_read_file(self) -> None:
        sandbox_manager = AsyncMock()
        sandbox_manager.read_file = AsyncMock(return_value="file contents")
        dispatcher = SandboxToolDispatcher(sandbox_manager, "sandbox-1")

        result = await dispatcher.dispatch("sandbox_read_file", {"path": "/workspace/foo.py"})

        assert result == "file contents"
        sandbox_manager.read_file.assert_awaited_once_with("sandbox-1", "/workspace/foo.py")

    async def test_dispatch_write_file(self) -> None:
        sandbox_manager = AsyncMock()
        sandbox_manager.write_file = AsyncMock()
        dispatcher = SandboxToolDispatcher(sandbox_manager, "sandbox-1")

        result = await dispatcher.dispatch(
            "sandbox_write_file", {"path": "/workspace/bar.py", "content": "print('hi')"}
        )

        assert result == "File written: /workspace/bar.py"
        sandbox_manager.write_file.assert_awaited_once_with(
            "sandbox-1", "/workspace/bar.py", "print('hi')"
        )

    async def test_dispatch_list_files(self) -> None:
        sandbox_manager = AsyncMock()
        sandbox_manager.list_files = AsyncMock(return_value=["a.py", "b.py"])
        dispatcher = SandboxToolDispatcher(sandbox_manager, "sandbox-1")

        result = await dispatcher.dispatch("sandbox_list_files", {})

        assert result == '["a.py", "b.py"]'
        sandbox_manager.list_files.assert_awaited_once_with("sandbox-1", "/workspace")

    async def test_dispatch_execute_command(self) -> None:
        from lintel.sandbox.types import SandboxResult

        sandbox_manager = AsyncMock()
        sandbox_manager.execute = AsyncMock(
            return_value=SandboxResult(exit_code=0, stdout="ok\n", stderr="")
        )
        dispatcher = SandboxToolDispatcher(sandbox_manager, "sandbox-1")

        result = await dispatcher.dispatch("sandbox_execute_command", {"command": "echo ok"})

        assert result == "ok\n"
        sandbox_manager.execute.assert_awaited_once()

    async def test_dispatch_unknown_tool_returns_error_json(self) -> None:
        sandbox_manager = AsyncMock()
        dispatcher = SandboxToolDispatcher(sandbox_manager, "sandbox-1")

        result = await dispatcher.dispatch("not_a_real_tool", {})

        assert "Unknown sandbox tool" in result
