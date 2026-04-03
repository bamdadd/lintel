"""Sub-session tool definitions for the agentic tool loop.

Provides tool schemas (in litellm/OpenAI format) and a dispatcher that
routes sub-session tool calls to SubSessionManager methods.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.agents.sub_sessions import SubSessionManager

SUB_SESSION_TOOL_PREFIX = "sub_session_"


def sub_session_tool_schemas() -> list[dict[str, Any]]:
    """Return litellm-format tool schemas for sub-session operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "sub_session_spawn",
                "description": (
                    "Spawn a child research session to investigate a repository. "
                    "Returns a session_id that can be polled for results."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "Repository to research (e.g. 'org/repo').",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Research prompt describing what to investigate.",
                        },
                    },
                    "required": ["repo", "prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sub_session_check_status",
                "description": (
                    "Check the status of a previously spawned sub-session. "
                    "Returns: pending, running, completed, or failed."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session_id returned by sub_session_spawn.",
                        },
                    },
                    "required": ["session_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sub_session_get_result",
                "description": (
                    "Get the findings from a completed sub-session. "
                    "Returns the research result text or an error message."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session_id returned by sub_session_spawn.",
                        },
                    },
                    "required": ["session_id"],
                },
            },
        },
    ]


def is_sub_session_tool(tool_name: str) -> bool:
    """Check if a tool name is a sub-session tool."""
    return tool_name.startswith(SUB_SESSION_TOOL_PREFIX)


class SubSessionToolDispatcher:
    """Routes sub-session tool calls to SubSessionManager methods."""

    def __init__(
        self,
        manager: SubSessionManager,
        parent_session_id: str,
    ) -> None:
        self._manager = manager
        self._parent_session_id = parent_session_id

    async def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a sub-session tool call and return the result as a string."""
        handlers = {
            "sub_session_spawn": self._spawn,
            "sub_session_check_status": self._check_status,
            "sub_session_get_result": self._get_result,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown sub-session tool: {tool_name}"})
        return await handler(arguments)

    async def _spawn(self, arguments: dict[str, Any]) -> str:
        repo = arguments.get("repo", "")
        prompt = arguments.get("prompt", "")
        if not repo or not prompt:
            return json.dumps({"error": "Both 'repo' and 'prompt' are required."})
        try:
            session = self._manager.spawn(self._parent_session_id, repo, prompt)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"session_id": session.session_id, "status": session.status.value})

    async def _check_status(self, arguments: dict[str, Any]) -> str:
        session_id = arguments.get("session_id", "")
        session = self._manager.get(session_id)
        if session is None:
            return json.dumps({"error": f"Sub-session not found: {session_id}"})
        return json.dumps({"session_id": session_id, "status": session.status.value})

    async def _get_result(self, arguments: dict[str, Any]) -> str:
        session_id = arguments.get("session_id", "")
        session = self._manager.get(session_id)
        if session is None:
            return json.dumps({"error": f"Sub-session not found: {session_id}"})
        if session.status == "completed":
            return json.dumps({"session_id": session_id, "result": session.result})
        if session.status == "failed":
            return json.dumps({"session_id": session_id, "error": session.error})
        return json.dumps(
            {
                "session_id": session_id,
                "status": session.status.value,
                "message": "Session not yet completed.",
            }
        )
