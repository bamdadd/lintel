"""Sub-session tool definitions for the agentic tool loop.

Provides tool schemas (in litellm/OpenAI format) and a dispatcher that
routes sub-session tool calls to the sub-session store.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

from lintel.domain.types import SubSession, SubSessionStatus

logger = structlog.get_logger()

SUB_SESSION_TOOL_PREFIX = "sub_session_"


def _all_sub_session_tool_schemas() -> list[dict[str, Any]]:
    """All available sub-session tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "sub_session_spawn",
                "description": (
                    "Spawn a child session to research a repo or explore "
                    "a parallel approach. Returns a session_id for polling."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_url": {
                            "type": "string",
                            "description": "Repository URL to research.",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Research prompt for the sub-session.",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sub_session_check_status",
                "description": "Check the current status of a sub-session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The sub-session ID returned by spawn.",
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
                    "Get the result of a completed sub-session. "
                    "Returns the findings text or error."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The sub-session ID returned by spawn.",
                        },
                    },
                    "required": ["session_id"],
                },
            },
        },
    ]


class SubSessionToolDispatcher:
    """Routes sub-session tool calls to the sub-session store."""

    def __init__(
        self,
        store: Any,
        parent_pipeline_run_id: str,
        max_sub_sessions: int = 10,
    ) -> None:
        self._store = store
        self._parent_pipeline_run_id = parent_pipeline_run_id
        self._max_sub_sessions = max_sub_sessions

    @classmethod
    def tool_schemas(cls) -> list[dict[str, Any]]:
        """Return litellm-format tool schemas for sub-session operations."""
        return _all_sub_session_tool_schemas()

    @classmethod
    def is_sub_session_tool(cls, tool_name: str) -> bool:
        """Check if a tool name is a sub-session tool."""
        return tool_name.startswith(SUB_SESSION_TOOL_PREFIX)

    async def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a sub-session tool call and return the result as a string."""
        handlers: dict[str, Any] = {
            "sub_session_spawn": self._spawn,
            "sub_session_check_status": self._check_status,
            "sub_session_get_result": self._get_result,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown sub-session tool: {tool_name}"})
        result: str = await handler(arguments)
        return result

    async def _spawn(self, arguments: dict[str, Any]) -> str:
        existing = await self._store.list_by_pipeline(self._parent_pipeline_run_id)
        if len(existing) >= self._max_sub_sessions:
            return json.dumps({
                "error": f"Maximum {self._max_sub_sessions} sub-sessions reached",
            })

        session_id = str(uuid.uuid4())
        sub_session = SubSession(
            session_id=session_id,
            parent_pipeline_run_id=self._parent_pipeline_run_id,
            repo_url=arguments.get("repo_url", ""),
            prompt=arguments["prompt"],
            status=SubSessionStatus.PENDING,
        )
        await self._store.add(sub_session)
        logger.info(
            "sub_session_spawned",
            session_id=session_id,
            pipeline_run_id=self._parent_pipeline_run_id,
        )
        return json.dumps({"session_id": session_id, "status": "pending"})

    async def _check_status(self, arguments: dict[str, Any]) -> str:
        session_id = arguments["session_id"]
        result = await self._store.get(session_id)
        if result is None:
            return json.dumps({"error": f"Sub-session {session_id} not found"})
        return json.dumps({"session_id": session_id, "status": result["status"]})

    async def _get_result(self, arguments: dict[str, Any]) -> str:
        session_id = arguments["session_id"]
        result = await self._store.get(session_id)
        if result is None:
            return json.dumps({"error": f"Sub-session {session_id} not found"})
        return json.dumps({
            "session_id": session_id,
            "status": result["status"],
            "result": result["result"],
            "error": result["error"],
        })


def sub_session_tool_schemas() -> list[dict[str, Any]]:
    """Return litellm-format tool schemas for sub-session operations."""
    return SubSessionToolDispatcher.tool_schemas()


def is_sub_session_tool(tool_name: str) -> bool:
    """Check if a tool name is a sub-session tool."""
    return SubSessionToolDispatcher.is_sub_session_tool(tool_name)
