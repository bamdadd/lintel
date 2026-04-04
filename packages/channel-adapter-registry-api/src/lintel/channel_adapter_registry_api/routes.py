"""Channel adapter registry CRUD and routing endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.channel_adapter_registry_api.types import ChannelAdapter

if TYPE_CHECKING:
    from lintel.channel_adapter_registry_api.store import InMemoryChannelAdapterStore

router = APIRouter()

adapter_store_provider: StoreProvider[InMemoryChannelAdapterStore] = StoreProvider()


class CreateAdapterRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    bot_id: str
    connection_id: str
    channel_type: str
    adapter_class: str = ""
    config: dict[str, Any] = {}
    enabled: bool = True
    priority: int = 0


class RouteRequest(BaseModel):
    bot_id: str
    channel_type: str


@router.post("/channel-adapters", status_code=201)
async def create_adapter(
    body: CreateAdapterRequest,
    store: InMemoryChannelAdapterStore = Depends(adapter_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Channel adapter already exists")
    dup = await store.find_by_bot_and_connection(body.bot_id, body.connection_id)
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail="Adapter already registered for this bot_id + connection_id",
        )
    now = datetime.now(UTC).isoformat()
    adapter = ChannelAdapter(
        id=body.id,
        bot_id=body.bot_id,
        connection_id=body.connection_id,
        channel_type=body.channel_type,
        adapter_class=body.adapter_class,
        config=body.config,
        enabled=body.enabled,
        priority=body.priority,
        created_at=now,
        updated_at=now,
    )
    await store.add(adapter)
    return asdict(adapter)


@router.get("/channel-adapters")
async def list_adapters(
    store: InMemoryChannelAdapterStore = Depends(adapter_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    adapters = await store.list_all()
    return [asdict(a) for a in adapters]


@router.get("/channel-adapters/{adapter_id}")
async def get_adapter(
    adapter_id: str,
    store: InMemoryChannelAdapterStore = Depends(adapter_store_provider),  # noqa: B008
) -> dict[str, Any]:
    adapter = await store.get(adapter_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Channel adapter not found")
    return asdict(adapter)


@router.post("/channel-adapters/route")
async def route_adapter(
    body: RouteRequest,
    store: InMemoryChannelAdapterStore = Depends(adapter_store_provider),  # noqa: B008
) -> dict[str, Any]:
    adapter = await store.route(body.bot_id, body.channel_type)
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail="No adapter found for this bot_id + channel_type",
        )
    return asdict(adapter)
