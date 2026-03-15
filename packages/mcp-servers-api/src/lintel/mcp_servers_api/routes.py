"""MCP server management endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import MCPServerRegistered, MCPServerRemoved, MCPServerUpdated
from lintel.domain.types import MCPServer

if TYPE_CHECKING:
    from lintel.mcp_servers_api.store import InMemoryMCPServerStore

router = APIRouter()

mcp_server_store_provider = StoreProvider()


class CreateMCPServerRequest(BaseModel):
    server_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    url: str
    enabled: bool = True
    description: str = ""
    config: dict[str, Any] = {}


class UpdateMCPServerRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None
    description: str | None = None
    config: dict[str, Any] | None = None


@router.post("/mcp-servers", status_code=201)
async def create_mcp_server(
    body: CreateMCPServerRequest,
    request: Request,
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register an MCP server."""
    existing = await store.get(body.server_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="MCP server already exists")
    server = MCPServer(
        server_id=body.server_id,
        name=body.name,
        url=body.url,
        enabled=body.enabled,
        description=body.description,
        config=body.config or None,
    )
    await store.add(server)
    await dispatch_event(
        request,
        MCPServerRegistered(payload={"resource_id": server.server_id}),
        stream_id=f"mcp_server:{server.server_id}",
    )
    return asdict(server)


@router.get("/mcp-servers")
async def list_mcp_servers(
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all configured MCP servers."""
    servers = await store.list_all()
    return [asdict(s) for s in servers]


@router.get("/mcp-servers/{server_id}")
async def get_mcp_server(
    server_id: str,
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific MCP server."""
    server = await store.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return asdict(server)


@router.patch("/mcp-servers/{server_id}")
async def update_mcp_server(
    server_id: str,
    body: UpdateMCPServerRequest,
    request: Request,
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update an MCP server's configuration."""
    server = await store.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    current = asdict(server)
    updates = body.model_dump(exclude_none=True)
    merged = {**current, **updates}
    updated = MCPServer(**merged)
    await store.update(updated)
    await dispatch_event(
        request,
        MCPServerUpdated(payload={"resource_id": server_id}),
        stream_id=f"mcp_server:{server_id}",
    )
    return asdict(updated)


@router.delete("/mcp-servers/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: str,
    request: Request,
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> None:
    """Remove an MCP server."""
    server = await store.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await store.remove(server_id)
    await dispatch_event(
        request,
        MCPServerRemoved(payload={"resource_id": server_id}),
        stream_id=f"mcp_server:{server_id}",
    )


@router.get("/mcp-servers/{server_id}/tools")
async def list_mcp_server_tools(
    server_id: str,
    request: Request,
    store: InMemoryMCPServerStore = Depends(mcp_server_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Fetch the list of tools from a remote MCP server."""
    server = await store.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    mcp_client = getattr(request.app.state, "mcp_tool_client", None)
    if mcp_client is None:
        raise HTTPException(status_code=501, detail="MCP tool client not configured")
    try:
        tools = await mcp_client.list_tools(server.url)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch tools from {server.url}: {exc}",
        ) from exc
    return list(tools)
