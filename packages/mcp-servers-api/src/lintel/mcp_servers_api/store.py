"""In-memory MCP server, tool catalog, and allowlist stores."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import MCPServer, MCPTool, MCPToolAllowlist


class InMemoryMCPServerStore:
    """In-memory store for MCP server configurations."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}

    async def add(self, server: MCPServer) -> None:
        self._servers[server.server_id] = server

    async def get(self, server_id: str) -> MCPServer | None:
        return self._servers.get(server_id)

    async def list_all(self) -> list[MCPServer]:
        return list(self._servers.values())

    async def list_enabled(self) -> list[MCPServer]:
        return [s for s in self._servers.values() if s.enabled]

    async def update(self, server: MCPServer) -> None:
        if server.server_id not in self._servers:
            msg = f"MCP server {server.server_id} not found"
            raise KeyError(msg)
        self._servers[server.server_id] = server

    async def remove(self, server_id: str) -> None:
        if server_id not in self._servers:
            msg = f"MCP server {server_id} not found"
            raise KeyError(msg)
        del self._servers[server_id]


class MCPToolStore:
    """In-memory catalog of MCP tools across all servers."""

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}

    async def add(self, tool: MCPTool) -> None:
        self._tools[tool.tool_id] = tool

    async def get(self, tool_id: str) -> MCPTool | None:
        return self._tools.get(tool_id)

    async def list_all(self) -> list[MCPTool]:
        return list(self._tools.values())

    async def list_by_server(self, server_id: str) -> list[MCPTool]:
        return [t for t in self._tools.values() if t.server_id == server_id]

    async def list_by_classification(self, classification: str) -> list[MCPTool]:
        return [t for t in self._tools.values() if t.security_classification == classification]

    async def remove(self, tool_id: str) -> bool:
        if tool_id not in self._tools:
            return False
        del self._tools[tool_id]
        return True


class MCPToolAllowlistStore:
    """In-memory store for per-project tool allowlists."""

    def __init__(self) -> None:
        self._allowlists: dict[str, MCPToolAllowlist] = {}

    async def set(self, allowlist: MCPToolAllowlist) -> None:
        # Remove any existing allowlist for the same project
        existing = await self.get_by_project(allowlist.project_id)
        if existing is not None:
            del self._allowlists[existing.allowlist_id]
        self._allowlists[allowlist.allowlist_id] = allowlist

    async def get(self, allowlist_id: str) -> MCPToolAllowlist | None:
        return self._allowlists.get(allowlist_id)

    async def get_by_project(self, project_id: str) -> MCPToolAllowlist | None:
        for al in self._allowlists.values():
            if al.project_id == project_id:
                return al
        return None

    async def list_all(self) -> list[MCPToolAllowlist]:
        return list(self._allowlists.values())

    async def remove(self, allowlist_id: str) -> bool:
        if allowlist_id not in self._allowlists:
            return False
        del self._allowlists[allowlist_id]
        return True
