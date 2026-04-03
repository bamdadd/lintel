"""Channel connection CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.channel_connections_api.types import ChannelConnection

if TYPE_CHECKING:
    from lintel.channel_connections_api.store import InMemoryChannelConnectionStore

router = APIRouter()

connection_store_provider: StoreProvider[InMemoryChannelConnectionStore] = StoreProvider()


class CreateChannelConnectionRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str
    channel_id: str
    workspace_id: str
    config: dict[str, Any] = {}


class UpdateChannelConnectionRequest(BaseModel):
    provider: str | None = None
    channel_id: str | None = None
    workspace_id: str | None = None
    config: dict[str, Any] | None = None


@router.post("/channel-connections", status_code=201)
async def create_channel_connection(
    body: CreateChannelConnectionRequest,
    store: InMemoryChannelConnectionStore = Depends(connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Channel connection already exists")
    now = datetime.now(UTC).isoformat()
    connection = ChannelConnection(
        id=body.id,
        provider=body.provider,
        channel_id=body.channel_id,
        workspace_id=body.workspace_id,
        config=body.config,
        created_at=now,
        updated_at=now,
    )
    await store.add(connection)
    return asdict(connection)


@router.get("/channel-connections")
async def list_channel_connections(
    store: InMemoryChannelConnectionStore = Depends(connection_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    connections = await store.list_all()
    return [asdict(c) for c in connections]


@router.get("/channel-connections/{connection_id}")
async def get_channel_connection(
    connection_id: str,
    store: InMemoryChannelConnectionStore = Depends(connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    connection = await store.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Channel connection not found")
    return asdict(connection)


@router.patch("/channel-connections/{connection_id}")
async def update_channel_connection(
    connection_id: str,
    body: UpdateChannelConnectionRequest,
    store: InMemoryChannelConnectionStore = Depends(connection_store_provider),  # noqa: B008
) -> dict[str, Any]:
    connection = await store.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Channel connection not found")
    updates = body.model_dump(exclude_none=True)
    updated = ChannelConnection(
        **{
            **asdict(connection),
            **updates,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    await store.update(updated)
    return asdict(updated)


@router.delete("/channel-connections/{connection_id}", status_code=204)
async def delete_channel_connection(
    connection_id: str,
    store: InMemoryChannelConnectionStore = Depends(connection_store_provider),  # noqa: B008
) -> None:
    connection = await store.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Channel connection not found")
    await store.remove(connection_id)
