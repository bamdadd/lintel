"""In-memory MCP server store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import MCPServer


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
