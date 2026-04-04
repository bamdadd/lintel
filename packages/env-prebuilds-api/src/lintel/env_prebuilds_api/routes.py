"""Environment prebuild CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.env_prebuilds_api.types import PrebuildConfig, PrebuildRun, PrebuildStatus

if TYPE_CHECKING:
    from lintel.env_prebuilds_api.store import InMemoryPrebuildConfigStore, InMemoryPrebuildRunStore

router = APIRouter()

prebuild_config_store_provider: StoreProvider[InMemoryPrebuildConfigStore] = StoreProvider()
prebuild_run_store_provider: StoreProvider[InMemoryPrebuildRunStore] = StoreProvider()


class CreatePrebuildConfigRequest(BaseModel):
    config_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    environment_id: str
    image: str = ""
    setup_commands: list[str] = Field(default_factory=list)
    warmup_count: int = 1


class TriggerPrebuildRequest(BaseModel):
    config_id: str


@router.post("/prebuilds/configs", status_code=201)
async def create_prebuild_config(
    body: CreatePrebuildConfigRequest,
    store: InMemoryPrebuildConfigStore = Depends(prebuild_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.config_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Prebuild config already exists")
    config = PrebuildConfig(
        config_id=body.config_id,
        name=body.name,
        environment_id=body.environment_id,
        image=body.image,
        setup_commands=body.setup_commands,
        warmup_count=body.warmup_count,
    )
    await store.add(config)
    return asdict(config)


@router.get("/prebuilds/configs")
async def list_prebuild_configs(
    store: InMemoryPrebuildConfigStore = Depends(prebuild_config_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    configs = await store.list_all()
    return [asdict(c) for c in configs]


@router.get("/prebuilds/configs/{config_id}")
async def get_prebuild_config(
    config_id: str,
    store: InMemoryPrebuildConfigStore = Depends(prebuild_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await store.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Prebuild config not found")
    return asdict(config)


@router.post("/prebuilds/trigger", status_code=201)
async def trigger_prebuild(
    body: TriggerPrebuildRequest,
    config_store: InMemoryPrebuildConfigStore = Depends(  # noqa: B008
        prebuild_config_store_provider,
    ),
    run_store: InMemoryPrebuildRunStore = Depends(prebuild_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await config_store.get(body.config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Prebuild config not found")
    run = PrebuildRun(
        run_id=str(uuid4()),
        config_id=body.config_id,
        status=PrebuildStatus.PENDING,
    )
    await run_store.add(run)
    return asdict(run)


@router.get("/prebuilds/status")
async def list_prebuild_status(
    config_id: str | None = None,
    store: InMemoryPrebuildRunStore = Depends(prebuild_run_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if config_id:
        runs = await store.list_by_config(config_id)
    else:
        runs = await store.list_all()
    return [asdict(r) for r in runs]
