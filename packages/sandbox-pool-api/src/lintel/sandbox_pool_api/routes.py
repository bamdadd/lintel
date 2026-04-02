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
    PooledSandboxAssigned,
    PooledSandboxReleased,
    SandboxImageBuilt,
    SandboxImageExpired,
    SandboxImageRebuildCompleted,
    SandboxImageRebuildFailed,
    SandboxImageRebuildStarted,
)
from lintel.domain.types import (
    ImageRebuildStatus,
    ImageRebuildTrigger,
    PooledSandbox,
    SandboxImage,
    SandboxPoolConfig,
    SandboxPoolStatus,
)
from lintel.sandbox_pool_api.store import (  # noqa: TC001
    InMemoryImageRebuildStore,
    InMemoryPooledSandboxStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)

router = APIRouter()

sandbox_image_store_provider: StoreProvider[InMemorySandboxImageStore] = StoreProvider()
pooled_sandbox_store_provider: StoreProvider[InMemoryPooledSandboxStore] = StoreProvider()
sandbox_pool_config_store_provider: StoreProvider[InMemorySandboxPoolConfigStore] = StoreProvider()
image_rebuild_store_provider: StoreProvider[InMemoryImageRebuildStore] = StoreProvider()


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
    rebuild_interval_seconds: int = Field(default=1800, ge=0)


class TriggerRebuildRequest(BaseModel):
    project_id: str
    commit_sha: str = ""
    branch: str = "main"


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


# --- Image rebuild routes (must be before {image_id} param route) ---


@router.post("/sandbox-pool/images/rebuild", status_code=201)
async def trigger_rebuild(
    request: Request,
    body: TriggerRebuildRequest,
    config_store: Annotated[
        InMemorySandboxPoolConfigStore, Depends(sandbox_pool_config_store_provider)
    ],
    rebuild_store: Annotated[InMemoryImageRebuildStore, Depends(image_rebuild_store_provider)],
    image_store: Annotated[InMemorySandboxImageStore, Depends(sandbox_image_store_provider)],
) -> dict[str, Any]:
    """Trigger a manual image rebuild for a project."""
    from lintel.sandbox_pool_api.scheduler import ImageRebuildScheduler

    scheduler = ImageRebuildScheduler(
        config_store=config_store,
        image_store=image_store,
        rebuild_store=rebuild_store,
    )

    await dispatch_event(
        request,
        SandboxImageRebuildStarted(
            payload={"project_id": body.project_id, "trigger": "manual"},
        ),
        stream_id=f"image-rebuild:{body.project_id}",
    )

    try:
        result = await scheduler.trigger_rebuild(
            body.project_id,
            trigger=ImageRebuildTrigger.MANUAL,
            commit_sha=body.commit_sha,
            branch=body.branch,
        )
    except (ValueError, RuntimeError) as exc:
        await dispatch_event(
            request,
            SandboxImageRebuildFailed(
                payload={"project_id": body.project_id, "error": str(exc)},
            ),
            stream_id=f"image-rebuild:{body.project_id}",
        )
        raise HTTPException(status_code=500, detail="Rebuild failed") from exc

    await dispatch_event(
        request,
        SandboxImageRebuildCompleted(
            payload={
                "project_id": body.project_id,
                "rebuild_id": result["rebuild_id"],
                "image_id": result["image_id"],
            },
        ),
        stream_id=f"image-rebuild:{body.project_id}",
    )
    return result


@router.get("/sandbox-pool/images/rebuild-status")
async def list_rebuild_records(
    rebuild_store: Annotated[InMemoryImageRebuildStore, Depends(image_rebuild_store_provider)],
    project_id: str | None = None,
    status: ImageRebuildStatus | None = None,
) -> list[dict[str, Any]]:
    """List image rebuild records, optionally filtered by project or status."""
    return await rebuild_store.list_all(project_id=project_id, status=status)


@router.get("/sandbox-pool/images/rebuild-status/{rebuild_id}")
async def get_rebuild_record(
    rebuild_id: str,
    rebuild_store: Annotated[InMemoryImageRebuildStore, Depends(image_rebuild_store_provider)],
) -> dict[str, Any]:
    """Get a specific rebuild record."""
    item = await rebuild_store.get(rebuild_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Rebuild record not found")
    return item


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
        rebuild_interval_seconds=body.rebuild_interval_seconds,
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
