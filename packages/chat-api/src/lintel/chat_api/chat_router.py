"""Chat router: classifies messages as direct chat replies or workflow triggers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.infrastructure.mcp.tool_client import MCPToolClient
    from lintel.mcp_servers_api.store import InMemoryMCPServerStore
    from lintel.models.router import DefaultModelRouter
    from lintel.models.types import ModelPolicy

logger = structlog.get_logger()

WORKFLOW_KEYWORDS: dict[str, list[str]] = {
    "feature_to_pr": ["build", "implement", "create", "add feature", "new feature", "develop"],
    "bug_fix": ["fix", "bug", "broken", "error", "crash", "regression"],
    "refactor": [
        "refactor",
        "clean up",
        "modernize",
        "restructure",
        "simplify",
        "remove the need",
        "get rid of",
        "eliminate",
    ],
    "code_review": ["review", "check code", "audit code", "look at the code"],
    "security_audit": ["security", "vulnerability", "cve", "penetration"],
    "documentation": ["document", "write docs", "update readme", "api docs"],
}


@dataclass(frozen=True)
class ChatRouterResult:
    """Result of classifying a chat message."""

    action: str  # "chat_reply" or "start_workflow"
    workflow_type: str = ""
    reply: str = ""


class ChatRouter:
    """Classifies chat messages and either replies directly or triggers a workflow."""

    def __init__(
        self,
        model_router: DefaultModelRouter | None = None,
        mcp_tool_client: MCPToolClient | None = None,
        mcp_server_store: InMemoryMCPServerStore | None = None,
    ) -> None:
        self._model_router = model_router
        self._mcp_tool_client = mcp_tool_client
        self._mcp_server_store = mcp_server_store

    async def classify(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
        enabled_workflows: set[str] | None = None,
    ) -> ChatRouterResult:
        keyword_result = self._classify_with_keywords(message, enabled_workflows)

        if self._model_router is not None:
            try:
                llm_result = await self._classify_with_llm(
                    message,
                    model_policy=model_policy,
                    api_base=api_base,
                    enabled_workflows=enabled_workflows,
                )
                # If keywords say it's a workflow but LLM says chat, trust keywords —
                # LLMs often misclassify actionable requests as chat replies
                if keyword_result.action == "start_workflow" and llm_result.action == "chat_reply":
                    logger.info(
                        "classify_override_llm_with_keywords",
                        llm_action=llm_result.action,
                        keyword_action=keyword_result.action,
                        workflow_type=keyword_result.workflow_type,
                    )
                    return keyword_result
                return llm_result
            except Exception:
                logger.warning("llm_classify_failed, falling back to keywords")

        return keyword_result

    async def _classify_with_llm(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
        enabled_workflows: set[str] | None = None,
    ) -> ChatRouterResult:
        from lintel.agents.types import AgentRole

        assert self._model_router is not None
        if model_policy is not None:
            policy = model_policy
        else:
            policy = await self._model_router.select_model(AgentRole.TRIAGE, "classify")

        active_keys = (
            {k for k in WORKFLOW_KEYWORDS if k in enabled_workflows}
            if enabled_workflows is not None
            else set(WORKFLOW_KEYWORDS.keys())
        )
        if not active_keys:
            # No workflows enabled — always chat reply
            return ChatRouterResult(action="chat_reply", reply="")
        workflow_types = ", ".join(active_keys)
        result = await self._model_router.call_model(
            policy,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a message classifier for a software engineering platform. "
                        "Classify the user message as either a simple question/chat OR "
                        "a task that requires a development workflow.\n\n"
                        "IMPORTANT: If the user is asking to CHANGE, MODIFY, BUILD, REMOVE, "
                        "ADD, FIX, REFACTOR, or DO anything to a codebase, that is ALWAYS "
                        "a workflow task — even if phrased casually. Only classify as "
                        "chat_reply if the user is asking a pure knowledge question.\n\n"
                        "If it's a pure knowledge question, respond with:\n"
                        "ACTION: chat_reply\n"
                        "REPLY: <your helpful answer>\n\n"
                        "If it requires a workflow (any code change request), respond with:\n"
                        f"ACTION: start_workflow\nWORKFLOW: <one of: {workflow_types}>\n"
                        "REPLY: <brief acknowledgment of what you'll do>\n\n"
                        "Examples of chat_reply: 'what is a deadlock?', "
                        "'how does git rebase work?', 'explain CQRS'\n"
                        "Examples of start_workflow: 'fix the login bug in auth.py', "
                        "'add a dark mode toggle to the settings page', "
                        "'refactor the database module', "
                        "'remove the need for workspaces', "
                        "'lets simplify the auth flow'"
                    ),
                },
                {"role": "user", "content": message},
            ],
            api_base=api_base,
        )

        return self._parse_llm_response(result.get("content", ""))

    def _parse_llm_response(self, content: str) -> ChatRouterResult:
        logger.info("classify_llm_raw_response", content=content[:500])

        action_match = re.search(r"ACTION:\s*(chat_reply|start_workflow)", content)
        workflow_match = re.search(r"WORKFLOW:\s*(\S+)", content)
        reply_match = re.search(r"REPLY:\s*(.+)", content, re.DOTALL)

        action = action_match.group(1) if action_match else ""
        workflow_type = workflow_match.group(1).strip() if workflow_match else ""
        reply = reply_match.group(1).strip() if reply_match else content.strip()

        # If LLM didn't follow the structured format, infer from content
        if not action:
            # If a WORKFLOW line was found, it's clearly a workflow
            if workflow_type or any(
                phrase in content.lower()
                for phrase in (
                    "refactor",
                    "implement",
                    "i'll help you",
                    "let's get started",
                    "i will help",
                    "let me",
                    "i can help you",
                    "start_workflow",
                    "workflow",
                )
            ):
                action = "start_workflow"
            else:
                action = "chat_reply"

        if action == "start_workflow" and workflow_type not in WORKFLOW_KEYWORDS:
            # Try to infer workflow type from the response content
            lower = content.lower()
            for wf_type, keywords in WORKFLOW_KEYWORDS.items():
                if any(kw in lower for kw in keywords):
                    workflow_type = wf_type
                    break
            else:
                workflow_type = "feature_to_pr"

        logger.info("classify_result", action=action, workflow_type=workflow_type)
        return ChatRouterResult(action=action, workflow_type=workflow_type, reply=reply)

    def _classify_with_keywords(
        self, message: str, enabled_workflows: set[str] | None = None
    ) -> ChatRouterResult:
        lower = message.lower()

        # Short messages or questions are likely chat
        if len(lower.split()) < 4 or lower.rstrip("?").endswith(("what", "how", "why", "when")):
            return ChatRouterResult(
                action="chat_reply",
                reply="I can help with that, but AI responses aren't connected yet. "
                "This will be answered by the LLM once fully wired.",
            )

        # Check for workflow keywords (only enabled ones)
        for workflow_type, keywords in WORKFLOW_KEYWORDS.items():
            if enabled_workflows is not None and workflow_type not in enabled_workflows:
                continue
            if any(kw in lower for kw in keywords):
                return ChatRouterResult(
                    action="start_workflow",
                    workflow_type=workflow_type,
                    reply=f"Starting **{workflow_type.replace('_', ' ')}** workflow...",
                )

        # Default: treat longer messages as tasks (only if feature_to_pr is enabled)
        if len(lower.split()) >= 8 and (
            enabled_workflows is None or "feature_to_pr" in enabled_workflows
        ):
            return ChatRouterResult(
                action="start_workflow",
                workflow_type="feature_to_pr",
                reply="Starting **feature to PR** workflow...",
            )

        return ChatRouterResult(
            action="chat_reply",
            reply="I can help with that, but AI responses aren't connected yet. "
            "This will be answered by the LLM once fully wired.",
        )

    # Read-only tools to pre-fetch for context (GET-like operations)
    _PREFETCH_TOOLS: tuple[str, ...] = (
        "models_list_models",
        "ai-providers_list_ai_providers",
        "agents_list_agent_definitions",
        "mcp-servers_list_mcp_servers",
        "skills_list_skills",
    )

    async def _gather_mcp_context(self) -> str:
        """Build context string from MCP servers: pre-fetched data + resources."""
        if self._mcp_tool_client is None or self._mcp_server_store is None:
            return ""
        try:
            servers = await self._mcp_server_store.list_enabled()
        except Exception:
            return ""
        if not servers:
            logger.info("mcp_context_no_enabled_servers")
            return ""

        logger.info("mcp_context_gathering", server_count=len(servers))
        parts: list[str] = []
        for server in servers:
            server_parts: list[str] = []

            # Pre-fetch real data from read-only tools
            try:
                logger.info("mcp_context_listing_tools", server=server.name, url=server.url)
                tools = await self._mcp_tool_client.list_tools(server.url)
                logger.info("mcp_context_tools_found", server=server.name, count=len(tools))
                tool_names = {t.get("name", "") for t in tools}
                for tool_name in self._PREFETCH_TOOLS:
                    if tool_name not in tool_names:
                        logger.info("mcp_prefetch_skip_not_found", tool=tool_name)
                        continue
                    try:
                        import json

                        logger.info("mcp_prefetch_calling", tool=tool_name, server=server.name)
                        result = await self._mcp_tool_client.call_tool(
                            server.url,
                            tool_name,
                            {},
                        )
                        content_parts = result.get("content", [])
                        if isinstance(content_parts, list):
                            text_parts = [
                                p.get("text", "")
                                for p in content_parts
                                if isinstance(p, dict) and p.get("type") == "text"
                            ]
                            text = "\n".join(text_parts)
                        else:
                            text = json.dumps(result)
                        if text:
                            label = tool_name.replace("_", " ").replace("-", " ").title()
                            logger.info(
                                "mcp_prefetch_success",
                                tool=tool_name,
                                chars=len(text),
                            )
                            if len(text) > 3000:
                                text = text[:3000] + "\n... (truncated)"
                            server_parts.append(f"{label}:\n{text}")
                        else:
                            logger.info("mcp_prefetch_empty", tool=tool_name)
                    except Exception as exc:
                        logger.warning("mcp_prefetch_failed", tool=tool_name, error=str(exc))

                # Summarize available tool count (don't list all 100+ tools)
                other_count = len(tools) - len(self._PREFETCH_TOOLS)
                if other_count > 0:
                    server_parts.append(
                        f"({other_count} additional API tools available on this server)"
                    )
            except Exception as exc:
                logger.warning("mcp_context_tools_failed", server=server.name, error=str(exc))

            # Gather resources
            try:
                resources = await self._mcp_tool_client.list_resources(
                    server.url,
                )
                for res in resources[:5]:
                    uri = res.get("uri", "")
                    if not uri:
                        continue
                    try:
                        content = await self._mcp_tool_client.read_resource(
                            server.url,
                            uri,
                        )
                        if content:
                            name = res.get("name", uri)
                            if len(content) > 2000:
                                content = content[:2000] + "\n... (truncated)"
                            server_parts.append(f"Resource '{name}':\n{content}")
                    except Exception:
                        logger.debug("mcp_resource_read_failed", uri=uri)
            except Exception:
                logger.debug("mcp_context_resources_failed", server=server.name)

            if server_parts:
                parts.append(f"[MCP Server: {server.name}]\n" + "\n\n".join(server_parts))

        return "\n\n".join(parts)

    async def _gather_mcp_tools(self) -> list[dict[str, object]]:
        """Collect tools from all enabled MCP servers."""
        if self._mcp_tool_client is None or self._mcp_server_store is None:
            logger.info("mcp_tools_skip_no_client_or_store")
            return []
        try:
            servers = await self._mcp_server_store.list_enabled()
            logger.info("mcp_tools_enabled_servers", count=len(servers))
        except Exception as exc:
            logger.warning("failed_to_list_mcp_servers", error=str(exc))
            return []
        all_tools: list[dict[str, object]] = []
        for server in servers:
            try:
                tools = await self._mcp_tool_client.get_tools_as_litellm_format(
                    server.url,
                )
                # Tag tools with server info for routing call_tool later
                for t in tools:
                    func = t.get("function", {})
                    if isinstance(func, dict):
                        func["_mcp_server_url"] = server.url
                        func["_mcp_server_name"] = server.name
                all_tools.extend(tools)
            except Exception:
                logger.warning("mcp_tool_fetch_failed", server=server.name, url=server.url)
        return all_tools

    async def _handle_tool_calls(
        self,
        tool_calls: list[dict[str, object]],
        mcp_tools: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        """Execute MCP tool calls and return tool result messages."""
        tool_url_map: dict[str, str] = {}
        for t in mcp_tools:
            func = t.get("function", {})
            if isinstance(func, dict):
                name = func.get("name", "")
                url = func.get("_mcp_server_url", "")
                if isinstance(name, str) and isinstance(url, str):
                    tool_url_map[name] = url

        results: list[dict[str, str]] = []
        for tc in tool_calls:
            import json

            fn = tc.get("function", {})
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name", ""))
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(str(args_raw)) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            server_url = tool_url_map.get(name, "")
            if not server_url or self._mcp_tool_client is None:
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id", "")),
                        "content": f"Error: No MCP server found for tool '{name}'",
                    }
                )
                continue
            try:
                result = await self._mcp_tool_client.call_tool(
                    server_url,
                    name,
                    args,
                )
                content_parts = result.get("content", [])
                if isinstance(content_parts, list):
                    text_parts = [
                        p.get("text", "")
                        for p in content_parts
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    content = "\n".join(text_parts) if text_parts else json.dumps(result)
                else:
                    content = json.dumps(result)
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id", "")),
                        "content": content,
                    }
                )
            except Exception as exc:
                logger.warning("mcp_tool_call_failed", tool=name, error=str(exc))
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id", "")),
                        "content": f"Error calling tool '{name}': {exc}",
                    }
                )
        return results

    async def reply(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
        project_context: str = "",
    ) -> str:
        """Generate a direct chat reply using the LLM, or return a fallback."""
        if self._model_router is None:
            return (
                "AI responses aren't connected yet. "
                "Configure an AI provider to enable chat replies."
            )

        from lintel.agents.types import AgentRole

        if model_policy is not None:
            policy = model_policy
        else:
            policy = await self._model_router.select_model(AgentRole.SUMMARIZER, "chat")

        logger.info("chat_reply_start", message_length=len(message))
        mcp_tools = await self._gather_mcp_tools()
        mcp_context = await self._gather_mcp_context()
        logger.info(
            "chat_reply_mcp_gathered",
            tool_count=len(mcp_tools),
            context_chars=len(mcp_context),
        )

        # Strip internal metadata before sending to LLM
        clean_tools: list[dict[str, object]] | None = None
        if mcp_tools:
            clean_tools = []
            for t in mcp_tools:
                func = t.get("function", {})
                if isinstance(func, dict):
                    clean_func = {k: v for k, v in func.items() if not k.startswith("_mcp_")}
                    clean_tools.append({"type": "function", "function": clean_func})

        system_prompt = (
            "You are a helpful software engineering assistant for the Lintel "
            "platform. Give concise, accurate answers. If the user is asking "
            "you to do development work (write code, fix bugs, etc.), tell them "
            "to phrase it as a task so the workflow pipeline can handle it.\n\n"
            "IMPORTANT: Never make up or hallucinate information. If you have tools "
            "available, use them to get real data before answering. If you don't have "
            "the information and can't look it up, say so honestly. When listing models, "
            "ONLY list models from the models endpoint — do NOT infer models from agent "
            "configurations or other sources."
        )
        if project_context:
            system_prompt += "\n\n" + project_context
        else:
            system_prompt += (
                "\n\nNo project is currently selected for this conversation. "
                "If the user asks about a specific project or wants to do work, "
                "ask them which project they're working on. Use the "
                "projects_list_projects tool (if available) to show them the "
                "available projects, then use projects_get_project to fetch "
                "details once they select one."
            )
        if mcp_context:
            system_prompt += (
                "\n\nThe following is REAL data from connected MCP servers. "
                "Use ONLY this information when answering questions about the platform. "
                "Do NOT make up information that isn't here:\n\n" + mcp_context
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        # Try with MCP tools if available; fall back to plain call if provider
        # doesn't support tool calling.
        result: dict[str, object] | None = None
        if clean_tools:
            try:
                result = await self._model_router.call_model(
                    policy,
                    messages=messages,
                    tools=clean_tools,
                    api_base=api_base,
                )
            except Exception:
                logger.warning("tool_call_unsupported_by_provider, retrying without tools")
                result = None

        if result is None:
            result = await self._model_router.call_model(
                policy,
                messages=messages,
                api_base=api_base,
            )

        # Handle tool calls if the model wants to use MCP tools
        tool_calls_raw = result.get("tool_calls")
        if tool_calls_raw and mcp_tools and isinstance(tool_calls_raw, list):
            tool_calls: list[dict[str, object]] = tool_calls_raw
            try:
                tool_results = await self._handle_tool_calls(tool_calls, mcp_tools)
                # Add assistant message with tool_calls so the provider sees the full turn
                assistant_msg: dict[str, object] = {
                    "role": "assistant",
                    "content": str(result.get("content", "") or ""),
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_msg)
                messages.extend(tool_results)
                result = await self._model_router.call_model(
                    policy,
                    messages=messages,
                    tools=clean_tools,
                    api_base=api_base,
                )
            except Exception:
                logger.exception("mcp_tool_round_trip_failed")

        return str(result.get("content", "Sorry, I couldn't generate a response."))

    async def reply_stream(
        self,
        message: str,
        model_policy: ModelPolicy | None = None,
        api_base: str | None = None,
        project_context: str = "",
    ) -> AsyncIterator[str]:
        """Stream a direct chat reply token by token."""
        if self._model_router is None:
            yield (
                "AI responses aren't connected yet. "
                "Configure an AI provider to enable chat replies."
            )
            return

        from lintel.agents.types import AgentRole

        if model_policy is not None:
            policy = model_policy
        else:
            policy = await self._model_router.select_model(AgentRole.SUMMARIZER, "chat")

        logger.info("chat_reply_stream_start", message_length=len(message))
        mcp_context = await self._gather_mcp_context()
        logger.info("chat_reply_stream_mcp_gathered", context_chars=len(mcp_context))

        system_prompt = (
            "You are a helpful software engineering assistant for the Lintel "
            "platform. Give concise, accurate answers. If the user is asking "
            "you to do development work (write code, fix bugs, etc.), tell them "
            "to phrase it as a task so the workflow pipeline can handle it.\n\n"
            "IMPORTANT: Never make up or hallucinate information. If you don't have "
            "the information, say so honestly. When listing models, ONLY list "
            "models from the models endpoint — do NOT infer models from agent "
            "configurations or other sources."
        )
        if project_context:
            system_prompt += "\n\n" + project_context
        else:
            system_prompt += (
                "\n\nNo project is currently selected for this conversation. "
                "If the user asks about a specific project or wants to do work, "
                "ask them which project they're working on. Use the "
                "projects_list_projects tool (if available) to show them the "
                "available projects, then use projects_get_project to fetch "
                "details once they select one."
            )
        if mcp_context:
            system_prompt += (
                "\n\nThe following is REAL data from connected MCP servers. "
                "Use ONLY this information when answering questions about the platform. "
                "Do NOT make up information that isn't here:\n\n" + mcp_context
            )

        async for token in self._model_router.stream_model(
            policy,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            api_base=api_base,
        ):
            yield token
