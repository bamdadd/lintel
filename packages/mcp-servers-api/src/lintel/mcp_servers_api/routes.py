"""MCP server management endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    MCPServerRegistered,
    MCPServerRemoved,
    MCPServerUpdated,
    MCPToolAllowlistUpdated,
    MCPToolRegistered,
    MCPToolRemoved,
)
from lintel.domain.types import MCPServer, MCPTool, MCPToolAllowlist

if TYPE_CHECKING:
    from lintel.mcp_servers_api.store import (
        InMemoryMCPServerStore,
        MCPToolAllowlistStore,
        MCPToolStore,
    )

router = APIRouter()

mcp_server_store_provider = StoreProvider()
mcp_tool_store_provider: StoreProvider[MCPToolStore] = StoreProvider()
mcp_tool_allowlist_store_provider: StoreProvider[MCPToolAllowlistStore] = StoreProvider()


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


# ---------------------------------------------------------------------------
# Tool catalog endpoints
# ---------------------------------------------------------------------------


class RegisterMCPToolRequest(BaseModel):
    tool_id: str = Field(default_factory=lambda: str(uuid4()))
    server_id: str
    name: str
    description: str = ""
    security_classification: str = "standard"
    enabled: bool = True


@router.post("/mcp-tools", status_code=201)
async def register_mcp_tool(
    body: RegisterMCPToolRequest,
    request: Request,
    store: MCPToolStore = Depends(mcp_tool_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register a tool in the catalog."""
    existing = await store.get(body.tool_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tool already exists")
    tool = MCPTool(
        tool_id=body.tool_id,
        server_id=body.server_id,
        name=body.name,
        description=body.description,
        security_classification=body.security_classification,
        enabled=body.enabled,
    )
    await store.add(tool)
    await dispatch_event(
        request,
        MCPToolRegistered(payload={"resource_id": tool.tool_id}),
        stream_id=f"mcp_tool:{tool.tool_id}",
    )
    return asdict(tool)


@router.get("/mcp-tools")
async def list_mcp_tools(
    server_id: str | None = None,
    classification: str | None = None,
    store: MCPToolStore = Depends(mcp_tool_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List catalogued tools, optionally filtered by server or classification."""
    if server_id:
        tools = await store.list_by_server(server_id)
    elif classification:
        tools = await store.list_by_classification(classification)
    else:
        tools = await store.list_all()
    return [asdict(t) for t in tools]


@router.get("/mcp-tools/{tool_id}")
async def get_mcp_tool(
    tool_id: str,
    store: MCPToolStore = Depends(mcp_tool_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific tool from the catalog."""
    tool = await store.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return asdict(tool)


@router.delete("/mcp-tools/{tool_id}", status_code=204)
async def delete_mcp_tool(
    tool_id: str,
    request: Request,
    store: MCPToolStore = Depends(mcp_tool_store_provider),  # noqa: B008
) -> None:
    """Remove a tool from the catalog."""
    removed = await store.remove(tool_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Tool not found")
    await dispatch_event(
        request,
        MCPToolRemoved(payload={"resource_id": tool_id}),
        stream_id=f"mcp_tool:{tool_id}",
    )


# ---------------------------------------------------------------------------
# Per-project tool allowlist endpoints
# ---------------------------------------------------------------------------


class SetAllowlistRequest(BaseModel):
    allowlist_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_ids: list[str] = []
    description: str = ""


@router.put("/projects/{project_id}/mcp-tool-allowlist")
async def set_project_allowlist(
    project_id: str,
    body: SetAllowlistRequest,
    request: Request,
    store: MCPToolAllowlistStore = Depends(mcp_tool_allowlist_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Set (create or replace) the tool allowlist for a project."""
    allowlist = MCPToolAllowlist(
        allowlist_id=body.allowlist_id,
        project_id=project_id,
        tool_ids=tuple(body.tool_ids),
        description=body.description,
    )
    await store.set(allowlist)
    await dispatch_event(
        request,
        MCPToolAllowlistUpdated(payload={"resource_id": project_id}),
        stream_id=f"mcp_allowlist:{project_id}",
    )
    return asdict(allowlist)


@router.get("/projects/{project_id}/mcp-tool-allowlist")
async def get_project_allowlist(
    project_id: str,
    store: MCPToolAllowlistStore = Depends(mcp_tool_allowlist_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get the tool allowlist for a project."""
    allowlist = await store.get_by_project(project_id)
    if allowlist is None:
        raise HTTPException(status_code=404, detail="No allowlist for project")
    return asdict(allowlist)


@router.delete("/projects/{project_id}/mcp-tool-allowlist", status_code=204)
async def delete_project_allowlist(
    project_id: str,
    request: Request,
    store: MCPToolAllowlistStore = Depends(mcp_tool_allowlist_store_provider),  # noqa: B008
) -> None:
    """Remove the tool allowlist for a project."""
    allowlist = await store.get_by_project(project_id)
    if allowlist is None:
        raise HTTPException(status_code=404, detail="No allowlist for project")
    await store.remove(allowlist.allowlist_id)
    await dispatch_event(
        request,
        MCPToolAllowlistUpdated(payload={"resource_id": project_id}),
        stream_id=f"mcp_allowlist:{project_id}",
    )


@router.get("/projects/{project_id}/mcp-tools")
async def list_project_tools(
    project_id: str,
    allowlist_store: MCPToolAllowlistStore = Depends(  # noqa: B008
        mcp_tool_allowlist_store_provider,
    ),
    tool_store: MCPToolStore = Depends(mcp_tool_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Resolve the effective tools available for a project.

    If the project has an allowlist, only return allowed + enabled tools.
    Otherwise return all enabled tools.
    """
    allowlist = await allowlist_store.get_by_project(project_id)
    all_tools = await tool_store.list_all()
    enabled = [t for t in all_tools if t.enabled]
    if allowlist is not None:
        allowed_ids = set(allowlist.tool_ids)
        enabled = [t for t in enabled if t.tool_id in allowed_ids]
    return [asdict(t) for t in enabled]
