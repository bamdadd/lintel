"""MCP tool client: discovers and calls tools on remote MCP servers."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class MCPToolClient:
    """Client that discovers and invokes tools on remote MCP servers via HTTP.

    Handles the MCP HTTP Streamable transport which requires session initialization.
    Sessions are cached per server URL.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}  # server_url -> session_id

    async def _ensure_session(self, client: httpx.AsyncClient, url: str) -> dict[str, str]:
        """Initialize an MCP session if we don't have one, return headers."""
        headers = dict(MCP_HEADERS)
        session_id = self._sessions.get(url)
        if session_id:
            headers["mcp-session-id"] = session_id
            return headers

        resp = await client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "lintel-mcp-client", "version": "0.1.0"},
                },
            },
            headers=headers,
        )
        resp.raise_for_status()
        session_id = resp.headers.get("mcp-session-id", "")
        if session_id:
            self._sessions[url] = session_id
            headers["mcp-session-id"] = session_id
        return headers

    async def _post(
        self,
        server_url: str,
        method: str,
        params: dict[str, Any],
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to an MCP server with session handling."""
        url = server_url.rstrip("/")
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = await self._ensure_session(client, url)
            resp = await client.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers=headers,
            )
            # If session expired, re-initialize and retry once
            if resp.status_code == 400:
                self._sessions.pop(url, None)
                headers = await self._ensure_session(client, url)
                resp = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    headers=headers,
                )
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            msg = data["error"].get("message", "Unknown MCP error")
            raise RuntimeError(msg)
        return data.get("result", {})  # type: ignore[no-any-return]

    async def list_tools(self, server_url: str) -> list[dict[str, Any]]:
        """Fetch available tools from an MCP server."""
        result = await self._post(server_url, "tools/list", {})
        tools = result.get("tools", [])
        return [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {}),
            }
            for t in tools
        ]

    async def call_tool(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a tool on an MCP server and return the result."""
        return await self._post(
            server_url,
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            timeout=30.0,
        )

    async def list_resources(self, server_url: str) -> list[dict[str, Any]]:
        """Fetch available resources from an MCP server."""
        try:
            result = await self._post(server_url, "resources/list", {})
            return result.get("resources", [])  # type: ignore[no-any-return]
        except Exception:
            logger.debug("resources_list_not_supported", url=server_url)
            return []

    async def read_resource(self, server_url: str, uri: str) -> str:
        """Read a specific resource from an MCP server."""
        result = await self._post(server_url, "resources/read", {"uri": uri})
        contents = result.get("contents", [])
        texts = [c.get("text", "") for c in contents if isinstance(c, dict)]
        return "\n".join(texts)

    async def get_tools_as_litellm_format(
        self,
        server_url: str,
    ) -> list[dict[str, Any]]:
        """Get tools in the OpenAI/litellm function-calling format."""
        tools = await self.list_tools(server_url)
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]
