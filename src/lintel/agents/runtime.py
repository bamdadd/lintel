"""Agent runtime: executes agent steps with model + tools + event emission."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.contracts.events import (
    AgentStepCompleted,
    AgentStepStarted,
    ModelCallCompleted,
    ModelSelected,
)
from lintel.contracts.types import ActorType

if TYPE_CHECKING:
    from uuid import UUID

    from lintel.contracts.protocols import EventStore, ModelRouter
    from lintel.contracts.types import AgentRole, ThreadRef
    from lintel.infrastructure.mcp.tool_client import MCPToolClient

logger = structlog.get_logger()


class AgentRuntime:
    """Executes agent steps, routing to models and emitting events."""

    def __init__(
        self,
        event_store: EventStore,
        model_router: ModelRouter,
        mcp_tool_client: MCPToolClient | None = None,
        mcp_server_store: Any = None,  # noqa: ANN401
    ) -> None:
        self._event_store = event_store
        self._model_router = model_router
        self._mcp_tool_client = mcp_tool_client
        self._mcp_server_store = mcp_server_store

    async def _gather_mcp_tools(self) -> list[dict[str, Any]]:
        """Collect tools from all enabled MCP servers in litellm format."""
        if self._mcp_tool_client is None or self._mcp_server_store is None:
            return []
        tools: list[dict[str, Any]] = []
        try:
            servers = await self._mcp_server_store.list_all()
            for server in servers:
                if isinstance(server, dict):
                    if not server.get("enabled", True):
                        continue
                    url = server.get("url", "")
                else:
                    if not getattr(server, "enabled", True):
                        continue
                    url = getattr(server, "url", "")
                if not url:
                    continue
                try:
                    server_tools = await self._mcp_tool_client.get_tools_as_litellm_format(url)
                    for t in server_tools:
                        t["_mcp_server_url"] = url
                    tools.extend(server_tools)
                except Exception:
                    logger.debug("mcp_tool_gather_failed", url=url)
        except Exception:
            logger.debug("mcp_server_list_failed")
        return tools

    async def execute_step(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        correlation_id: UUID | None = None,
    ) -> dict[str, Any]:
        cid = correlation_id or uuid4()

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepStarted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                    },
                )
            ],
        )

        policy = await self._model_router.select_model(agent_role, step_name)
        await self._event_store.append(
            thread_ref.stream_id,
            [
                ModelSelected(
                    actor_type=ActorType.SYSTEM,
                    actor_id="model_router",
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "provider": policy.provider,
                        "model_name": policy.model_name,
                    },
                )
            ],
        )

        # Merge MCP tools with any explicitly passed tools.
        # Pass tools=[] to explicitly disable all tools (including MCP).
        # Pass tools=None to auto-discover MCP tools.
        # Pass tools=[...] to use those tools AND merge MCP tools.
        all_tools = list(tools) if tools else []
        if tools is None or len(tools) > 0:
            mcp_tools = await self._gather_mcp_tools()
        else:
            mcp_tools = []
        if mcp_tools:
            all_tools.extend(mcp_tools)
            logger.info(
                "mcp_tools_injected",
                agent_role=agent_role.value,
                step_name=step_name,
                tool_count=len(mcp_tools),
            )

        result = await self._model_router.call_model(
            policy,
            messages,
            all_tools or None,
        )

        await self._event_store.append(
            thread_ref.stream_id,
            [
                ModelCallCompleted(
                    actor_type=ActorType.SYSTEM,
                    actor_id="model_router",
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "provider": policy.provider,
                        "model": result.get("model", policy.model_name),
                        "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                        "output_tokens": result.get("usage", {}).get("output_tokens", 0),
                        "mcp_tools_available": len(mcp_tools),
                    },
                )
            ],
        )

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepCompleted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                        "output_summary": result.get("content", "")[:500],
                    },
                )
            ],
        )

        return result

    async def execute_step_stream(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, str]],
        on_chunk: Any | None = None,  # noqa: ANN401 — async callable(str) -> None
        correlation_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Like execute_step but streams content, calling on_chunk for each piece.

        Returns the same result dict as execute_step, with the full accumulated content.
        The on_chunk callback receives partial text as it arrives from the model.
        """
        cid = correlation_id or uuid4()

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepStarted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                        "streaming": True,
                    },
                )
            ],
        )

        policy = await self._model_router.select_model(agent_role, step_name)
        await self._event_store.append(
            thread_ref.stream_id,
            [
                ModelSelected(
                    actor_type=ActorType.SYSTEM,
                    actor_id="model_router",
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "provider": policy.provider,
                        "model_name": policy.model_name,
                        "streaming": True,
                    },
                )
            ],
        )

        # Stream content from model
        accumulated = []
        async for chunk in self._model_router.stream_model(policy, messages):
            accumulated.append(chunk)
            if on_chunk is not None:
                await on_chunk(chunk)

        full_content = "".join(accumulated)

        # No usage info from streaming — estimate from content length
        result: dict[str, Any] = {
            "content": full_content,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "model": policy.model_name,
        }

        await self._event_store.append(
            thread_ref.stream_id,
            [
                AgentStepCompleted(
                    actor_type=ActorType.AGENT,
                    actor_id=agent_role.value,
                    thread_ref=thread_ref,
                    correlation_id=cid,
                    payload={
                        "agent_role": agent_role.value,
                        "step_name": step_name,
                        "output_summary": full_content[:500],
                    },
                )
            ],
        )

        return result
