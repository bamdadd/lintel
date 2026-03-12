"""Agent runtime: executes agent steps with model + tools + event emission."""

from __future__ import annotations

import json
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
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from lintel.contracts.protocols import EventStore, ModelRouter, SandboxManager
    from lintel.contracts.types import AgentRole, ThreadRef
    from lintel.contracts.workflow_models import AgentStepResult
    from lintel.infrastructure.mcp.tool_client import MCPToolClient

logger = structlog.get_logger()

DEFAULT_MAX_TOOL_ITERATIONS = 20


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

    async def _execute_tool_call(
        self,
        tool_call: dict[str, Any],
        all_tools: list[dict[str, Any]],
        sandbox_manager: SandboxManager | None,
        sandbox_id: str | None,
    ) -> str:
        """Dispatch a single tool call and return the result string."""
        from lintel.agents.sandbox_tools import dispatch_sandbox_tool, is_sandbox_tool

        func = tool_call.get("function", {})
        name = func.get("name", "")
        raw_args = func.get("arguments", "{}")
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            return f"Invalid JSON arguments: {raw_args}"

        # Sandbox tools
        if is_sandbox_tool(name):
            if sandbox_manager is None or sandbox_id is None:
                return f"Sandbox not available for tool: {name}"
            try:
                return await dispatch_sandbox_tool(sandbox_manager, sandbox_id, name, arguments)
            except Exception as exc:
                logger.warning("sandbox_tool_error", tool=name, error=str(exc))
                return f"Error executing {name}: {exc}"

        # MCP tools — find the server URL from the tool metadata
        if self._mcp_tool_client is not None:
            server_url = None
            for t in all_tools:
                if t.get("function", {}).get("name") == name:
                    server_url = t.get("_mcp_server_url")
                    break
            if server_url:
                try:
                    result = await self._mcp_tool_client.call_tool(server_url, name, arguments)
                    return json.dumps(result)
                except Exception as exc:
                    logger.warning("mcp_tool_error", tool=name, error=str(exc))
                    return f"Error executing {name}: {exc}"

        return f"Unknown tool: {name}"

    async def execute_step(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        correlation_id: UUID | None = None,
        sandbox_manager: SandboxManager | None = None,
        sandbox_id: str | None = None,
        max_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
        on_tool_call: Callable[[int, str, dict[str, Any], str], Awaitable[None]] | None = None,
        on_activity: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentStepResult:
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
        # Only inject MCP tools when no explicit tools are passed (tools=None).
        # When tools are explicitly provided (even if non-empty), trust the caller.
        all_tools = list(tools) if tools else []
        if tools is None:
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

        # Build conversation messages (mutable copy for the tool loop)
        loop_messages: list[dict[str, Any]] = list(messages)
        total_input_tokens = 0
        total_output_tokens = 0
        iteration = 0

        # Pass sandbox context for providers that need it (e.g. claude_code)
        model_kwargs: dict[str, Any] = {}
        if sandbox_manager is not None:
            model_kwargs["sandbox_manager"] = sandbox_manager
        if sandbox_id is not None:
            model_kwargs["sandbox_id"] = sandbox_id
        if on_activity is not None:
            model_kwargs["on_activity"] = on_activity

        is_claude_code = policy.provider == "claude_code"

        result = await self._model_router.call_model(
            policy,
            loop_messages,
            all_tools or None,
            **model_kwargs,
        )
        total_input_tokens += result.get("usage", {}).get("input_tokens", 0)
        total_output_tokens += result.get("usage", {}).get("output_tokens", 0)

        has_tool_calls = bool(result.get("tool_calls"))
        logger.info(
            "model_initial_response",
            step_name=step_name,
            has_tool_calls=has_tool_calls,
            tool_count=len(result.get("tool_calls", [])),
            content_length=len(result.get("content", "") or ""),
            tools_provided=len(all_tools),
        )

        # Claude Code handles its own tool loop — skip ours
        if is_claude_code:
            result["tool_iterations"] = 0
            # Skip to event emission below

        # Tool execution loop (litellm providers only)
        while not is_claude_code and result.get("tool_calls") and iteration < max_iterations:
            iteration += 1
            tool_calls = result["tool_calls"]

            # Append assistant message with tool calls
            loop_messages.append(
                {
                    "role": "assistant",
                    "content": result.get("content") or None,
                    "tool_calls": tool_calls,
                }
            )

            # Execute each tool call and append results
            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "?")
                logger.info(
                    "tool_call_executing",
                    iteration=iteration,
                    tool=func_name,
                    step_name=step_name,
                )
                tool_result = await self._execute_tool_call(
                    tc, all_tools, sandbox_manager, sandbox_id
                )
                logger.info(
                    "tool_call_completed",
                    iteration=iteration,
                    tool=func_name,
                    result_length=len(tool_result),
                    step_name=step_name,
                )
                if on_tool_call is not None:
                    raw_args = tc.get("function", {}).get("arguments", "{}")
                    try:
                        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}
                    await on_tool_call(iteration, func_name, tool_args, tool_result)
                loop_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    }
                )

            logger.info(
                "tool_loop_iteration",
                iteration=iteration,
                tool_count=len(tool_calls),
                step_name=step_name,
            )

            # Call model again with updated messages
            result = await self._model_router.call_model(
                policy,
                loop_messages,
                all_tools or None,
                **model_kwargs,
            )
            total_input_tokens += result.get("usage", {}).get("input_tokens", 0)
            total_output_tokens += result.get("usage", {}).get("output_tokens", 0)

        if iteration >= max_iterations and result.get("tool_calls"):
            logger.warning(
                "tool_loop_max_iterations",
                max_iterations=max_iterations,
                step_name=step_name,
            )

        # Aggregate usage across all iterations
        result["usage"] = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        }
        result["tool_iterations"] = iteration

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
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "mcp_tools_available": len(mcp_tools),
                        "tool_iterations": iteration,
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
                        "output_summary": (result.get("content") or "")[:500],
                    },
                )
            ],
        )

        from lintel.contracts.workflow_models import AgentStepResult, TokenUsage

        return AgentStepResult(
            content=result.get("content", "") or "",
            model=result.get("model", policy.model_name),
            usage=TokenUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_input_tokens + total_output_tokens,
            ),
            tool_calls=result.get("tool_calls", []) or [],
            tool_iterations=iteration,
        )

    async def execute_step_stream(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, str]],
        on_chunk: Any | None = None,  # noqa: ANN401 — async callable(str) -> None
        correlation_id: UUID | None = None,
        sandbox_manager: SandboxManager | None = None,
        sandbox_id: str | None = None,
        on_activity: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentStepResult:
        """Like execute_step but streams content, calling on_chunk for each piece.

        Returns the same result dict as execute_step, with the full accumulated content.
        The on_chunk callback receives partial text as it arrives from the model.

        For providers that don't support streaming (e.g. claude_code), falls back
        to a non-streaming call and delivers the full content as a single chunk.
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

        # Claude Code uses invoke_streaming via on_activity callback
        if policy.provider == "claude_code":
            model_kwargs: dict[str, Any] = {}
            if sandbox_manager is not None:
                model_kwargs["sandbox_manager"] = sandbox_manager
            if sandbox_id is not None:
                model_kwargs["sandbox_id"] = sandbox_id
            if on_activity is not None:
                model_kwargs["on_activity"] = on_activity
            result = await self._model_router.call_model(policy, messages, None, **model_kwargs)
            full_content = result.get("content", "")
            if on_chunk is not None and full_content:
                await on_chunk(full_content)
        else:
            # Stream content from model
            accumulated = []
            async for chunk in self._model_router.stream_model(policy, messages):
                accumulated.append(chunk)
                if on_chunk is not None:
                    await on_chunk(chunk)
            full_content = "".join(accumulated)

            # Read usage from the model router (captured from final stream chunk)
            stream_usage = getattr(self._model_router, "last_stream_usage", None)
            if not isinstance(stream_usage, dict):
                stream_usage = {}
            result = {
                "content": full_content,
                "usage": {
                    "input_tokens": stream_usage.get("input_tokens", 0),
                    "output_tokens": stream_usage.get("output_tokens", 0),
                },
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

        from lintel.contracts.workflow_models import AgentStepResult, TokenUsage

        usage_data = result.get("usage", {})
        return AgentStepResult(
            content=result.get("content", "") or "",
            model=result.get("model", policy.model_name),
            usage=TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            ),
            tool_calls=result.get("tool_calls", []) or [],
            tool_iterations=result.get("tool_iterations", 0),
        )
