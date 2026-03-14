"""Settings and connections management endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.data_models import ConnectionData
from lintel.contracts.events import (
    ConnectionCreated,
    ConnectionRemoved,
    ConnectionUpdated,
    SettingsUpdated,
)

router = APIRouter()


def get_connections(request: Request) -> dict[str, dict[str, Any]]:
    """Get connections registry from app state."""
    if not hasattr(request.app.state, "connections"):
        request.app.state.connections = {}
    return request.app.state.connections  # type: ignore[no-any-return]


def get_general_settings(request: Request) -> dict[str, Any]:
    """Get general settings from app state."""
    if not hasattr(request.app.state, "general_settings"):
        from lintel.contracts.data_models import GeneralSettings

        request.app.state.general_settings = GeneralSettings().model_dump()
    return request.app.state.general_settings  # type: ignore[no-any-return]


class ConnectionRequest(BaseModel):
    connection_id: str
    connection_type: str  # slack, github, llm_provider, postgres, etc.
    name: str
    config: dict[str, Any] = {}


class UpdateConnectionRequest(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None


class UpdateSettingsRequest(BaseModel):
    workspace_name: str | None = None
    default_model_provider: str | None = None
    pii_detection_enabled: bool | None = None
    sandbox_enabled: bool | None = None
    max_concurrent_workflows: int | None = None
    max_sandboxes: int | None = None


@router.post("/settings/connections", status_code=201)
async def create_connection(body: ConnectionRequest, request: Request) -> dict[str, Any]:
    """Register a new external connection."""
    connections = get_connections(request)
    if body.connection_id in connections:
        raise HTTPException(status_code=409, detail="Connection already exists")
    conn_data = ConnectionData(
        connection_id=body.connection_id,
        connection_type=body.connection_type,
        name=body.name,
        config=body.config,
        status="untested",
    )
    entry = conn_data.model_dump()
    connections[body.connection_id] = entry
    await dispatch_event(
        request,
        ConnectionCreated(payload={"resource_id": body.connection_id}),
        stream_id=f"connection:{body.connection_id}",
    )
    return entry


@router.get("/settings/connections")
async def list_connections(request: Request) -> list[dict[str, Any]]:
    """List all registered connections."""
    return list(get_connections(request).values())


@router.get("/settings/connections/{connection_id}")
async def get_connection(connection_id: str, request: Request) -> dict[str, Any]:
    """Get a specific connection."""
    connections = get_connections(request)
    if connection_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connections[connection_id]


@router.patch("/settings/connections/{connection_id}")
async def update_connection(
    connection_id: str, body: UpdateConnectionRequest, request: Request
) -> dict[str, Any]:
    """Update an existing connection."""
    connections = get_connections(request)
    if connection_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    conn = connections[connection_id]
    if body.name is not None:
        conn["name"] = body.name
    if body.config is not None:
        conn["config"] = body.config
    await dispatch_event(
        request,
        ConnectionUpdated(payload={"resource_id": connection_id}),
        stream_id=f"connection:{connection_id}",
    )
    return conn


@router.delete("/settings/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: str, request: Request) -> None:
    """Remove a connection."""
    connections = get_connections(request)
    if connection_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    del connections[connection_id]
    await dispatch_event(
        request,
        ConnectionRemoved(payload={"resource_id": connection_id}),
        stream_id=f"connection:{connection_id}",
    )


@router.post("/settings/connections/{connection_id}/test")
async def test_connection(connection_id: str, request: Request) -> dict[str, Any]:
    """Test a connection (dry-run)."""
    connections = get_connections(request)
    if connection_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    connections[connection_id]["status"] = "ok"
    return {
        "connection_id": connection_id,
        "status": "ok",
        "message": "Connection test successful (dry-run)",
    }


@router.get("/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    """Get general platform settings."""
    return get_general_settings(request)


@router.patch("/settings")
async def update_settings(body: UpdateSettingsRequest, request: Request) -> dict[str, Any]:
    """Update general platform settings."""
    settings = get_general_settings(request)
    for key, value in body.model_dump(exclude_none=True).items():
        settings[key] = value
    await dispatch_event(
        request,
        SettingsUpdated(payload={}),
        stream_id="settings",
    )
    return settings
