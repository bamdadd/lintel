"""Database replica configuration CRUD endpoints for sandbox projects."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.sandboxes_api.replica_store import DatabaseReplicaConfig, InMemoryReplicaConfigStore

router = APIRouter()

replica_config_store_provider: StoreProvider = StoreProvider()


class CreateReplicaConfigRequest(BaseModel):
    replica_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    name: str
    host: str
    port: int = 5432
    database: str = "postgres"
    read_only: bool = True
    credential_ref: str = ""


class UpdateReplicaConfigRequest(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    read_only: bool | None = None
    credential_ref: str | None = None


@router.post("/projects/{project_id}/replica-configs", status_code=201)
async def create_replica_config(
    project_id: str,
    body: CreateReplicaConfigRequest,
    store: InMemoryReplicaConfigStore = Depends(replica_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    if body.project_id != project_id:
        body = body.model_copy(update={"project_id": project_id})
    existing = await store.get(body.replica_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Replica config already exists")
    replica = DatabaseReplicaConfig(
        replica_id=body.replica_id,
        project_id=project_id,
        name=body.name,
        host=body.host,
        port=body.port,
        database=body.database,
        read_only=body.read_only,
        credential_ref=body.credential_ref,
    )
    await store.add(replica)
    return asdict(replica)


@router.get("/projects/{project_id}/replica-configs")
async def list_replica_configs(
    project_id: str,
    store: InMemoryReplicaConfigStore = Depends(replica_config_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    replicas = await store.list_for_project(project_id)
    return [asdict(r) for r in replicas]


@router.get("/projects/{project_id}/replica-configs/{replica_id}")
async def get_replica_config(
    project_id: str,
    replica_id: str,
    store: InMemoryReplicaConfigStore = Depends(replica_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    replica = await store.get(replica_id)
    if replica is None or replica.project_id != project_id:
        raise HTTPException(status_code=404, detail="Replica config not found")
    return asdict(replica)


@router.patch("/projects/{project_id}/replica-configs/{replica_id}")
async def update_replica_config(
    project_id: str,
    replica_id: str,
    body: UpdateReplicaConfigRequest,
    store: InMemoryReplicaConfigStore = Depends(replica_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    replica = await store.get(replica_id)
    if replica is None or replica.project_id != project_id:
        raise HTTPException(status_code=404, detail="Replica config not found")
    updates = body.model_dump(exclude_none=True)
    updated = DatabaseReplicaConfig(**{**asdict(replica), **updates})
    await store.update(updated)
    return asdict(updated)


@router.delete("/projects/{project_id}/replica-configs/{replica_id}", status_code=204)
async def delete_replica_config(
    project_id: str,
    replica_id: str,
    store: InMemoryReplicaConfigStore = Depends(replica_config_store_provider),  # noqa: B008
) -> None:
    replica = await store.get(replica_id)
    if replica is None or replica.project_id != project_id:
        raise HTTPException(status_code=404, detail="Replica config not found")
    await store.remove(replica_id)
