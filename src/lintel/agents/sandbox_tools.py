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


def sandbox_tool_schemas() -> list[dict[str, Any]]:
    """Return litellm-format tool schemas for sandbox operations."""
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


def is_sandbox_tool(tool_name: str) -> bool:
    """Check if a tool name is a sandbox-backed tool."""
    return tool_name.startswith(SANDBOX_TOOL_PREFIX)


async def dispatch_sandbox_tool(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a sandbox tool call and return the result as a string."""
    from lintel.contracts.types import SandboxJob

    if tool_name == "sandbox_read_file":
        content = await sandbox_manager.read_file(sandbox_id, arguments["path"])
        return content

    if tool_name == "sandbox_write_file":
        await sandbox_manager.write_file(sandbox_id, arguments["path"], arguments["content"])
        return f"File written: {arguments['path']}"

    if tool_name == "sandbox_list_files":
        path = arguments.get("path", "/workspace")
        files = await sandbox_manager.list_files(sandbox_id, path)
        return json.dumps(files)

    if tool_name == "sandbox_execute_command":
        result = await sandbox_manager.execute(
            sandbox_id,
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

    return json.dumps({"error": f"Unknown sandbox tool: {tool_name}"})
