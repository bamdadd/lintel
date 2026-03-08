"""Tests for MCP tool injection in AgentRuntime."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from lintel.agents.runtime import AgentRuntime
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


@pytest.fixture()
def mock_event_store() -> AsyncMock:
    store = AsyncMock()
    store.append = AsyncMock()
    return store


@pytest.fixture()
def mock_model_router() -> AsyncMock:
    router = AsyncMock()
    router.select_model = AsyncMock(
        return_value=ModelPolicy(
            provider="test", model_name="test-model", max_tokens=100,
        ),
    )
    router.call_model = AsyncMock(
        return_value={
            "content": "test response",
            "model": "test-model",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    return router


@pytest.fixture()
def thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="w1", channel_id="c1", thread_ts="t1")


class TestMCPToolGathering:
    async def test_gather_mcp_tools_no_client(
        self,
        mock_event_store: AsyncMock,
        mock_model_router: AsyncMock,
    ) -> None:
        """No MCP client returns empty list."""
        runtime = AgentRuntime(
            event_store=mock_event_store,
            model_router=mock_model_router,
        )
        tools = await runtime._gather_mcp_tools()
        assert tools == []

    async def test_gather_mcp_tools_from_servers(
        self,
        mock_event_store: AsyncMock,
        mock_model_router: AsyncMock,
    ) -> None:
        """Gathers tools from enabled MCP servers."""
        mcp_client = AsyncMock()
        mcp_client.get_tools_as_litellm_format = AsyncMock(
            return_value=[
                {
                    "type": "function",
                    "function": {"name": "search", "description": "Search code"},
                },
            ],
        )

        server_store = AsyncMock()
        server_store.list_all = AsyncMock(
            return_value=[
                {"url": "http://mcp:8080", "enabled": True, "name": "test"},
            ],
        )

        runtime = AgentRuntime(
            event_store=mock_event_store,
            model_router=mock_model_router,
            mcp_tool_client=mcp_client,
            mcp_server_store=server_store,
        )
        tools = await runtime._gather_mcp_tools()
        assert len(tools) == 1
        assert tools[0]["_mcp_server_url"] == "http://mcp:8080"

    async def test_gather_skips_disabled_servers(
        self,
        mock_event_store: AsyncMock,
        mock_model_router: AsyncMock,
    ) -> None:
        """Skips disabled MCP servers."""
        mcp_client = AsyncMock()
        server_store = AsyncMock()
        server_store.list_all = AsyncMock(
            return_value=[
                {"url": "http://mcp:8080", "enabled": False, "name": "disabled"},
            ],
        )

        runtime = AgentRuntime(
            event_store=mock_event_store,
            model_router=mock_model_router,
            mcp_tool_client=mcp_client,
            mcp_server_store=server_store,
        )
        tools = await runtime._gather_mcp_tools()
        assert tools == []

    async def test_execute_step_merges_mcp_tools(
        self,
        mock_event_store: AsyncMock,
        mock_model_router: AsyncMock,
        thread_ref: ThreadRef,
    ) -> None:
        """MCP tools are merged with explicit tools in execute_step."""
        mcp_client = AsyncMock()
        mcp_client.get_tools_as_litellm_format = AsyncMock(
            return_value=[
                {
                    "type": "function",
                    "function": {"name": "mcp_tool", "description": "MCP"},
                },
            ],
        )
        server_store = AsyncMock()
        server_store.list_all = AsyncMock(
            return_value=[{"url": "http://mcp:8080", "enabled": True, "name": "s"}],
        )

        runtime = AgentRuntime(
            event_store=mock_event_store,
            model_router=mock_model_router,
            mcp_tool_client=mcp_client,
            mcp_server_store=server_store,
        )

        explicit_tool: dict[str, Any] = {
            "type": "function",
            "function": {"name": "local_tool", "description": "Local"},
        }

        await runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="implement",
            messages=[{"role": "user", "content": "write code"}],
            tools=[explicit_tool],
        )

        # call_model should have been called with merged tools
        call_args = mock_model_router.call_model.call_args
        tools_passed = call_args[0][2]  # third positional arg
        assert len(tools_passed) == 2
        tool_names = [t["function"]["name"] for t in tools_passed]
        assert "local_tool" in tool_names
        assert "mcp_tool" in tool_names
