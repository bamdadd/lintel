"""Sandbox pool CRUD endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    ImageBuildScheduleTriggered,
    PooledSandboxAssigned,
    PooledSandboxReleased,
    SandboxImageBuilt,
    SandboxImageExpired,
)
from lintel.domain.types import (
    ImageBuildSchedule,
    PooledSandbox,
    SandboxImage,
    SandboxPoolConfig,
    SandboxPoolStatus,
)
from lintel.sandbox_pool_api.store import (  # noqa: TC001
    InMemoryImageBuildScheduleStore,
    InMemoryPooledSandboxStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)

router = APIRouter()

sandbox_image_store_provider: StoreProvider[InMemorySandboxImageStore] = StoreProvider()
pooled_sandbox_store_provider: StoreProvider[InMemoryPooledSandboxStore] = StoreProvider()
sandbox_pool_config_store_provider: StoreProvider[InMemorySandboxPoolConfigStore] = StoreProvider()
image_build_schedule_store_provider: StoreProvider[InMemoryImageBuildScheduleStore] = (
    StoreProvider()
)


# --- Request models ---


class CreateSandboxImageRequest(BaseModel):
    repository_url: str
    branch: str = "main"
    commit_sha: str = ""
    image_tag: str = ""
    size_mb: int = Field(default=0, ge=0)
    build_duration_seconds: int = Field(default=0, ge=0)


class AcquireSandboxRequest(BaseModel):
    project_id: str
    pipeline_run_id: str


class UpdatePoolConfigRequest(BaseModel):
    min_warm: int = Field(default=2, ge=0)
    max_warm: int = Field(default=5, ge=1)
    ttl_seconds: int = Field(default=3600, ge=60)
    auto_rebuild_on_push: bool = True


# --- Image routes ---


@router.post("/sandbox-pool/images", status_code=201)
async def create_image(
    request: Request,
    body: CreateSandboxImageRequest,
    store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> dict[str, Any]:
    image_id = str(uuid4())
    now = datetime.now(UTC)
    image = SandboxImage(
        image_id=image_id,
        repository_url=body.repository_url,
        branch=body.branch,
        commit_sha=body.commit_sha,
        image_tag=body.image_tag or image_id[:12],
        size_mb=body.size_mb,
        build_duration_seconds=body.build_duration_seconds,
        created_at=now,
    )
    result = await store.add(image)
    await dispatch_event(
        request,
        SandboxImageBuilt(payload={"resource_id": image_id, "repository_url": body.repository_url}),
        stream_id=f"sandbox-image:{image_id}",
    )
    return result


@router.get("/sandbox-pool/images")
async def list_images(
    store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/sandbox-pool/images/{image_id}")
async def get_image(
    image_id: str,
    store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> dict[str, Any]:
    item = await store.get(image_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sandbox image not found")
    return item


@router.delete("/sandbox-pool/images/{image_id}", status_code=204)
async def delete_image(
    request: Request,
    image_id: str,
    store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> None:
    if not await store.remove(image_id):
        raise HTTPException(status_code=404, detail="Sandbox image not found")
    await dispatch_event(
        request,
        SandboxImageExpired(payload={"resource_id": image_id}),
        stream_id=f"sandbox-image:{image_id}",
    )


# --- Pooled sandbox routes ---


@router.get("/sandbox-pool/sandboxes")
async def list_sandboxes(
    store: Annotated[InMemoryPooledSandboxStore, Depends(pooled_sandbox_store_provider)],
    status: SandboxPoolStatus | None = None,
) -> list[dict[str, Any]]:
    return await store.list_all(status=status)


@router.post("/sandbox-pool/sandboxes/acquire", status_code=200)
async def acquire_sandbox(
    request: Request,
    body: AcquireSandboxRequest,
    store: Annotated[InMemoryPooledSandboxStore, Depends(pooled_sandbox_store_provider)],
) -> dict[str, Any]:
    candidate = await store.acquire_warm(body.project_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="No warm sandbox available for this project")
    sandbox_id = candidate["sandbox_id"]
    updated = await store.update(
        sandbox_id,
        {
            "status": SandboxPoolStatus.IN_USE,
            "assigned_pipeline_run_id": body.pipeline_run_id,
        },
    )
    assert updated is not None
    await dispatch_event(
        request,
        PooledSandboxAssigned(
            payload={
                "resource_id": sandbox_id,
                "pipeline_run_id": body.pipeline_run_id,
            },
        ),
        stream_id=f"pooled-sandbox:{sandbox_id}",
    )
    return updated


@router.post("/sandbox-pool/sandboxes/{sandbox_id}/release", status_code=200)
async def release_sandbox(
    request: Request,
    sandbox_id: str,
    store: Annotated[InMemoryPooledSandboxStore, Depends(pooled_sandbox_store_provider)],
) -> dict[str, Any]:
    current = await store.get(sandbox_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Pooled sandbox not found")
    updated = await store.update(
        sandbox_id,
        {"status": SandboxPoolStatus.READY, "assigned_pipeline_run_id": ""},
    )
    assert updated is not None
    await dispatch_event(
        request,
        PooledSandboxReleased(payload={"resource_id": sandbox_id}),
        stream_id=f"pooled-sandbox:{sandbox_id}",
    )
    return updated


# --- Pool config routes ---


@router.get("/sandbox-pool/config/{project_id}")
async def get_pool_config(
    project_id: str,
    store: Annotated[InMemorySandboxPoolConfigStore, Depends(sandbox_pool_config_store_provider)],
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Pool config not found")
    return item


@router.put("/sandbox-pool/config/{project_id}")
async def update_pool_config(
    project_id: str,
    body: UpdatePoolConfigRequest,
    store: Annotated[InMemorySandboxPoolConfigStore, Depends(sandbox_pool_config_store_provider)],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    existing = await store.get(project_id)
    created_at = datetime.fromisoformat(existing["created_at"]) if existing else now
    config = SandboxPoolConfig(
        config_id=existing["config_id"] if existing else str(uuid4()),
        project_id=project_id,
        min_warm=body.min_warm,
        max_warm=body.max_warm,
        ttl_seconds=body.ttl_seconds,
        auto_rebuild_on_push=body.auto_rebuild_on_push,
        created_at=created_at,
        updated_at=now,
    )
    return await store.upsert(config)


# --- Helper to seed a warm sandbox (used by tests / internal) ---


async def _seed_warm_sandbox(
    store: InMemoryPooledSandboxStore,
    *,
    image_id: str,
    project_id: str,
) -> PooledSandbox:
    """Create a ready pooled sandbox — convenience for tests and internal seeding."""
    now = datetime.now(UTC)
    sb = PooledSandbox(
        sandbox_id=str(uuid4()),
        image_id=image_id,
        status=SandboxPoolStatus.READY,
        project_id=project_id,
        created_at=now,
        last_heartbeat=now,
    )
    await store.add(sb)
    return sb


# --- Image build schedule routes ---


class CreateBuildScheduleRequest(BaseModel):
    schedule_id: str = Field(default_factory=lambda: str(uuid4()))
    repository_url: str
    cron_expression: str = "*/30 * * * *"
    branch: str = "main"
    enabled: bool = True


@router.post("/sandbox-pool/schedules", status_code=201)
async def create_build_schedule(
    body: CreateBuildScheduleRequest,
    store: Annotated[InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)],
) -> dict[str, Any]:
    """Create an image build schedule."""
    existing = await store.get(body.schedule_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Schedule already exists")
    schedule = ImageBuildSchedule(
        schedule_id=body.schedule_id,
        repository_url=body.repository_url,
        cron_expression=body.cron_expression,
        branch=body.branch,
        enabled=body.enabled,
    )
    return await store.add(schedule)


@router.get("/sandbox-pool/schedules")
async def list_build_schedules(
    store: Annotated[InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)],
) -> list[dict[str, Any]]:
    """List all image build schedules."""
    return await store.list_all()


@router.get("/sandbox-pool/schedules/{schedule_id}")
async def get_build_schedule(
    schedule_id: str,
    store: Annotated[InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)],
) -> dict[str, Any]:
    """Get a specific build schedule."""
    item = await store.get(schedule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")
    return item


@router.patch("/sandbox-pool/schedules/{schedule_id}")
async def update_build_schedule(
    schedule_id: str,
    body: dict[str, Any],
    store: Annotated[InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)],
) -> dict[str, Any]:
    """Update a build schedule."""
    updated = await store.update(schedule_id, body)
    if updated is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")
    return updated


@router.delete("/sandbox-pool/schedules/{schedule_id}", status_code=204)
async def delete_build_schedule(
    schedule_id: str,
    store: Annotated[InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)],
) -> None:
    """Delete a build schedule."""
    if not await store.remove(schedule_id):
        raise HTTPException(status_code=404, detail="Build schedule not found")


@router.post("/sandbox-pool/schedules/{schedule_id}/trigger")
async def trigger_build(
    schedule_id: str,
    request: Request,
    sched_store: Annotated[
        InMemoryImageBuildScheduleStore, Depends(image_build_schedule_store_provider)
    ],
    image_store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> dict[str, Any]:
    """Manually trigger an image build for a schedule."""
    item = await sched_store.get(schedule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    now = datetime.now(UTC)
    image_id = str(uuid4())
    image = SandboxImage(
        image_id=image_id,
        repository_url=item["repository_url"],
        branch=item["branch"],
        commit_sha="",
        image_tag=image_id[:12],
        created_at=now,
    )
    result = await image_store.add(image)

    await sched_store.update(schedule_id, {"last_built_at": now})
    await dispatch_event(
        request,
        ImageBuildScheduleTriggered(
            payload={"resource_id": schedule_id, "image_id": image_id},
        ),
        stream_id=f"build-schedule:{schedule_id}",
    )
    return {"schedule_id": schedule_id, "image": result}
