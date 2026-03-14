"""Sandbox-backed tool definitions for the agentic tool loop.

Provides tool schemas (in litellm/OpenAI format) and a dispatcher that
routes tool calls to SandboxManager methods.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager

logger = structlog.get_logger()

SANDBOX_TOOL_PREFIX = "sandbox_"


def _all_sandbox_tool_schemas() -> list[dict[str, Any]]:
    """All available sandbox tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "sandbox_read_file",
                "description": "Read the contents of a file in the sandbox workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to read.",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sandbox_write_file",
                "description": "Write content to a file in the sandbox workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to write.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sandbox_list_files",
                "description": "List files in a directory in the sandbox workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list. Defaults to /workspace.",
                            "default": "/workspace",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sandbox_execute_command",
                "description": "Execute a shell command in the sandbox workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute.",
                        },
                        "workdir": {
                            "type": "string",
                            "description": "Working directory. Defaults to /workspace.",
                            "default": "/workspace",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
    ]


class SandboxToolDispatcher:
    """Routes tool calls to SandboxManager methods."""

    def __init__(self, sandbox_manager: SandboxManager, sandbox_id: str) -> None:
        self._manager = sandbox_manager
        self._sandbox_id = sandbox_id

    @classmethod
    def tool_schemas(cls, exclude: set[str] | None = None) -> list[dict[str, Any]]:
        """Return litellm-format tool schemas for sandbox operations.

        Args:
            exclude: Tool names to omit (e.g. {"sandbox_list_files"}).
        """
        _exclude = exclude or set()
        return [s for s in _all_sandbox_tool_schemas() if s["function"]["name"] not in _exclude]

    @classmethod
    def is_sandbox_tool(cls, tool_name: str) -> bool:
        """Check if a tool name is a sandbox-backed tool."""
        return tool_name.startswith(SANDBOX_TOOL_PREFIX)

    async def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a sandbox tool call and return the result as a string."""
        handlers: dict[str, Any] = {
            "sandbox_read_file": self._read_file,
            "sandbox_write_file": self._write_file,
            "sandbox_list_files": self._list_files,
            "sandbox_execute_command": self._execute_command,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown sandbox tool: {tool_name}"})
        return await handler(arguments)

    async def _read_file(self, arguments: dict[str, Any]) -> str:
        content = await self._manager.read_file(self._sandbox_id, arguments["path"])
        return content

    async def _write_file(self, arguments: dict[str, Any]) -> str:
        await self._manager.write_file(self._sandbox_id, arguments["path"], arguments["content"])
        return f"File written: {arguments['path']}"

    async def _list_files(self, arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "/workspace")
        files = await self._manager.list_files(self._sandbox_id, path)
        return json.dumps(files)

    async def _execute_command(self, arguments: dict[str, Any]) -> str:
        from lintel.contracts.types import SandboxJob

        result = await self._manager.execute(
            self._sandbox_id,
            SandboxJob(
                command=arguments["command"],
                workdir=arguments.get("workdir", "/workspace"),
            ),
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.exit_code != 0:
            output += f"\n[exit code: {result.exit_code}]"
        return output


# ---------------------------------------------------------------------------
# Backward-compatible module-level wrappers
# ---------------------------------------------------------------------------


def sandbox_tool_schemas(
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return litellm-format tool schemas for sandbox operations.

    Args:
        exclude: Tool names to omit (e.g. {"sandbox_list_files"}).
    """
    return SandboxToolDispatcher.tool_schemas(exclude=exclude)


def is_sandbox_tool(tool_name: str) -> bool:
    """Check if a tool name is a sandbox-backed tool."""
    return SandboxToolDispatcher.is_sandbox_tool(tool_name)


async def dispatch_sandbox_tool(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a sandbox tool call and return the result as a string."""
    dispatcher = SandboxToolDispatcher(sandbox_manager, sandbox_id)
    return await dispatcher.dispatch(tool_name, arguments)
