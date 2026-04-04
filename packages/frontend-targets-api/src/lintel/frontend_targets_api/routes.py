"""Frontend target CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    FrontendTargetCreated,
    FrontendTargetRemoved,
    FrontendTargetUpdated,
)
from lintel.domain.types import FrontendPlatform, FrontendTarget
from lintel.frontend_targets_api.store import InMemoryFrontendTargetStore

router = APIRouter()

frontend_target_store_provider: StoreProvider = StoreProvider()

VALID_PLATFORMS = {p.value for p in FrontendPlatform}


class CreateFrontendTargetRequest(BaseModel):
    target_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    platform: str
    label: str = ""
    config: dict[str, object] = Field(default_factory=dict)


class UpdateFrontendTargetRequest(BaseModel):
    label: str | None = None
    platform: str | None = None
    config: dict[str, object] | None = None


@router.post("/frontend-targets", status_code=201)
async def create_frontend_target(
    body: CreateFrontendTargetRequest,
    request: Request,
    store: InMemoryFrontendTargetStore = Depends(frontend_target_store_provider),  # noqa: B008
) -> dict[str, Any]:
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid platform. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}",
        )
    existing = await store.get(body.target_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Frontend target already exists")
    target = FrontendTarget(
        target_id=body.target_id,
        project_id=body.project_id,
        platform=body.platform,
        label=body.label,
        config=body.config,
    )
    await store.add(target)
    await dispatch_event(
        request,
        FrontendTargetCreated(payload={"resource_id": target.target_id}),
        stream_id=f"frontend-target:{target.target_id}",
    )
    return asdict(target)


@router.get("/frontend-targets")
async def list_frontend_targets(
    store: InMemoryFrontendTargetStore = Depends(frontend_target_store_provider),  # noqa: B008
    project_id: str | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    targets = await store.list_all(project_id=project_id, platform=platform)
    return [asdict(t) for t in targets]


@router.get("/frontend-targets/{target_id}")
async def get_frontend_target(
    target_id: str,
    store: InMemoryFrontendTargetStore = Depends(frontend_target_store_provider),  # noqa: B008
) -> dict[str, Any]:
    target = await store.get(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Frontend target not found")
    return asdict(target)


@router.patch("/frontend-targets/{target_id}")
async def update_frontend_target(
    target_id: str,
    body: UpdateFrontendTargetRequest,
    request: Request,
    store: InMemoryFrontendTargetStore = Depends(frontend_target_store_provider),  # noqa: B008
) -> dict[str, Any]:
    target = await store.get(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Frontend target not found")
    updates = body.model_dump(exclude_none=True)
    if "platform" in updates and updates["platform"] not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid platform. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}",
        )
    updated = FrontendTarget(**{**asdict(target), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        FrontendTargetUpdated(payload={"resource_id": target_id}),
        stream_id=f"frontend-target:{target_id}",
    )
    return asdict(updated)


@router.delete("/frontend-targets/{target_id}", status_code=204)
async def delete_frontend_target(
    target_id: str,
    request: Request,
    store: InMemoryFrontendTargetStore = Depends(frontend_target_store_provider),  # noqa: B008
) -> None:
    target = await store.get(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Frontend target not found")
    await store.remove(target_id)
    await dispatch_event(
        request,
        FrontendTargetRemoved(payload={"resource_id": target_id}),
        stream_id=f"frontend-target:{target_id}",
    )
