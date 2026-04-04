"""Board sync CRUD and trigger endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.board_sync_api.types import ConflictStrategy, SyncDirection, SyncProvider, SyncStatus

if TYPE_CHECKING:
    from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore

router = APIRouter()

sync_config_store_provider: StoreProvider[BoardSyncConfigStore] = StoreProvider()
mapping_store_provider: StoreProvider[ExternalIdMappingStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateSyncConfigRequest(BaseModel):
    sync_config_id: str = Field(default_factory=lambda: uuid4().hex)
    board_id: str
    provider: SyncProvider
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS
    connection_id: str = ""
    external_project_key: str = ""
    external_database_id: str = ""


class UpdateSyncConfigRequest(BaseModel):
    direction: SyncDirection | None = None
    conflict_strategy: ConflictStrategy | None = None
    connection_id: str | None = None
    external_project_key: str | None = None
    external_database_id: str | None = None


class SyncConfigResponse(BaseModel):
    sync_config_id: str
    board_id: str
    provider: str
    direction: str
    conflict_strategy: str
    connection_id: str
    external_project_key: str
    external_database_id: str
    status: str
    last_synced: str
    items_in_sync: int


class TriggerSyncResponse(BaseModel):
    pulled: int
    pushed: int
    status: str


class MappingResponse(BaseModel):
    mapping_id: str
    sync_config_id: str
    work_item_id: str
    external_id: str
    last_synced: str


# ---------------------------------------------------------------------------
# Sync config CRUD
# ---------------------------------------------------------------------------


@router.post("/board-sync/configs", status_code=201)
async def create_sync_config(
    body: CreateSyncConfigRequest,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await config_store.get(body.sync_config_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Sync config already exists")
    data: dict[str, Any] = {
        "sync_config_id": body.sync_config_id,
        "board_id": body.board_id,
        "provider": body.provider.value,
        "direction": body.direction.value,
        "conflict_strategy": body.conflict_strategy.value,
        "connection_id": body.connection_id,
        "external_project_key": body.external_project_key,
        "external_database_id": body.external_database_id,
        "status": SyncStatus.DISCONNECTED.value,
        "last_synced": "",
        "items_in_sync": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await config_store.add(data)
    return data


@router.get("/board-sync/configs")
async def list_sync_configs(
    board_id: str | None = None,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if board_id:
        return await config_store.list_by_board(board_id)
    return await config_store.list_all()


@router.get("/board-sync/configs/{sync_config_id}")
async def get_sync_config(
    sync_config_id: str,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    return config


@router.patch("/board-sync/configs/{sync_config_id}")
async def update_sync_config(
    sync_config_id: str,
    body: UpdateSyncConfigRequest,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    updates = body.model_dump(exclude_none=True)
    # Convert enums to values
    for k, v in updates.items():
        if hasattr(v, "value"):
            updates[k] = v.value
    merged = {**config, **updates}
    await config_store.update(sync_config_id, merged)
    return merged


@router.delete("/board-sync/configs/{sync_config_id}", status_code=204)
async def delete_sync_config(
    sync_config_id: str,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
) -> None:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    await config_store.remove(sync_config_id)


# ---------------------------------------------------------------------------
# Trigger sync
# ---------------------------------------------------------------------------


@router.post("/board-sync/configs/{sync_config_id}/sync")
async def trigger_sync(
    sync_config_id: str,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
    mapping_store: ExternalIdMappingStore = Depends(mapping_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    from lintel.board_sync_api.sync_engine import SyncEngine

    engine = SyncEngine(config_store, mapping_store)
    result = await engine.sync(sync_config_id, work_items=[])
    return result


# ---------------------------------------------------------------------------
# External ID mappings
# ---------------------------------------------------------------------------


@router.get("/board-sync/configs/{sync_config_id}/mappings")
async def list_mappings(
    sync_config_id: str,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
    mapping_store: ExternalIdMappingStore = Depends(mapping_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    return await mapping_store.list_by_config(sync_config_id)


@router.post("/board-sync/configs/{sync_config_id}/mappings", status_code=201)
async def create_mapping(
    sync_config_id: str,
    work_item_id: str,
    external_id: str,
    config_store: BoardSyncConfigStore = Depends(sync_config_store_provider),  # noqa: B008
    mapping_store: ExternalIdMappingStore = Depends(mapping_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await config_store.get(sync_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Sync config not found")
    mapping: dict[str, Any] = {
        "mapping_id": uuid4().hex,
        "sync_config_id": sync_config_id,
        "work_item_id": work_item_id,
        "external_id": external_id,
        "last_synced": datetime.now(UTC).isoformat(),
    }
    await mapping_store.add(mapping)
    return mapping
