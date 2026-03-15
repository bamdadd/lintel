"""Memory tools for agent recall and storage.

Provides tool schemas (in litellm/OpenAI format) and a dispatcher that
routes tool calls to MemoryService methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.memory.memory_service import MemoryService

logger = structlog.get_logger()

MEMORY_TOOL_PREFIX = "memory_"

MEMORY_TOOL_NAMES = frozenset({"recall_memory", "store_memory"})


def _all_memory_tool_schemas() -> list[dict[str, Any]]:
    """All available memory tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "recall_memory",
                "description": (
                    "Search project memory for relevant context. Use this when you need"
                    " to recall past decisions, patterns, issues, or learnings from"
                    " previous workflows. Returns concise summaries to avoid context bloat."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for - describe the context you need",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID to search memories for",
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["long_term", "episodic", "all"],
                            "description": (
                                "Type of memory to search. 'long_term' for"
                                " patterns/conventions, 'episodic' for past task recalls,"
                                " 'all' for both."
                            ),
                            "default": "all",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results to return",
                            "default": 5,
                        },
                    },
                    "required": ["query", "project_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "store_memory",
                "description": (
                    "Save an important discovery, pattern, or learning to project memory"
                    " for future reference. Use this when you discover something valuable"
                    " that should be remembered across workflows."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project UUID",
                        },
                        "content": {
                            "type": "string",
                            "description": "The fact, pattern, or learning to remember",
                        },
                        "fact_type": {
                            "type": "string",
                            "description": (
                                "Category: 'pattern', 'convention', 'issue', 'preference',"
                                " 'architecture', 'dependency'"
                            ),
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["long_term", "episodic"],
                            "description": (
                                "long_term for persistent patterns, episodic for"
                                " task-specific recalls"
                            ),
                            "default": "long_term",
                        },
                    },
                    "required": ["project_id", "content", "fact_type"],
                },
            },
        },
    ]


class MemoryToolDispatcher:
    """Routes tool calls to MemoryService methods."""

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory_service = memory_service

    @classmethod
    def tool_schemas(cls, exclude: set[str] | None = None) -> list[dict[str, Any]]:
        """Return litellm-format tool schemas for memory operations.

        Args:
            exclude: Tool names to omit (e.g. {"store_memory"}).
        """
        _exclude = exclude or set()
        return [s for s in _all_memory_tool_schemas() if s["function"]["name"] not in _exclude]

    @classmethod
    def is_memory_tool(cls, tool_name: str) -> bool:
        """Check if a tool name is a memory-backed tool."""
        return tool_name in MEMORY_TOOL_NAMES

    async def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a memory tool call and return the result as a string."""
        handlers: dict[str, Any] = {
            "recall_memory": self._recall,
            "store_memory": self._store,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return f"Unknown memory tool: {tool_name}"
        result: str = await handler(arguments)
        return result

    async def _recall(self, arguments: dict[str, Any]) -> str:
        from uuid import UUID

        from lintel.memory.models import MemoryType

        project_id = UUID(arguments["project_id"])
        query = arguments["query"]
        memory_type_str = arguments.get("memory_type", "all")
        top_k = arguments.get("top_k", 5)

        memory_type = None
        if memory_type_str != "all":
            memory_type = MemoryType(memory_type_str)

        chunks = await self._memory_service.recall(
            project_id=project_id,
            query=query,
            memory_type=memory_type,
            top_k=top_k,
        )

        if not chunks:
            return "No relevant memories found."

        # Format concisely for LLM consumption
        lines = ["Relevant memories:"]
        for chunk in chunks:
            fact = chunk.fact
            source = " (from workflow)" if fact.source_workflow_id else ""
            lines.append(
                f"- [{fact.fact_type}] {fact.content}{source} (relevance: {chunk.score:.2f})"
            )
        return "\n".join(lines)

    async def _store(self, arguments: dict[str, Any]) -> str:
        from uuid import UUID

        from lintel.memory.models import MemoryType

        project_id = UUID(arguments["project_id"])
        content = arguments["content"]
        fact_type = arguments["fact_type"]
        memory_type = MemoryType(arguments.get("memory_type", "long_term"))

        fact = await self._memory_service.store_memory(
            project_id=project_id,
            content=content,
            memory_type=memory_type,
            fact_type=fact_type,
        )
        return f"Memory stored: [{fact.fact_type}] {fact.content[:100]}..."


# ---------------------------------------------------------------------------
# Backward-compatible module-level wrappers
# ---------------------------------------------------------------------------


def memory_tool_schemas(
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return litellm-format tool schemas for memory operations.

    Args:
        exclude: Tool names to omit (e.g. {"store_memory"}).
    """
    return MemoryToolDispatcher.tool_schemas(exclude=exclude)


def is_memory_tool(tool_name: str) -> bool:
    """Check if a tool name is a memory-backed tool."""
    return MemoryToolDispatcher.is_memory_tool(tool_name)


async def dispatch_memory_tool(
    memory_service: MemoryService,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a memory tool call and return the result as a string."""
    dispatcher = MemoryToolDispatcher(memory_service)
    return await dispatcher.dispatch(tool_name, arguments)
