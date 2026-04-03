"""Sandbox session snapshot endpoints: create, list, get, restore, delete."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    SandboxSnapshotCreated,
    SandboxSnapshotExpired,
    SandboxSnapshotRestored,
)
from lintel.domain.types import SandboxSnapshot, SandboxSnapshotStatus

if TYPE_CHECKING:
    from .snapshot_store import InMemorySnapshotStore

router = APIRouter()

snapshot_store_provider: StoreProvider[InMemorySnapshotStore] = StoreProvider()


class CreateSnapshotRequest(BaseModel):
    pipeline_run_id: str = ""
    project_id: str = ""
    commit_sha: str = ""
    ttl_seconds: int = 86400


@router.post("/sandboxes/{sandbox_id}/snapshot", status_code=201)
async def create_snapshot(
    sandbox_id: str,
    body: CreateSnapshotRequest,
    request: Request,
) -> dict[str, Any]:
    """Create a snapshot of the sandbox filesystem state."""
    store = snapshot_store_provider.get()
    snapshot_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=body.ttl_seconds)

    snapshot = SandboxSnapshot(
        snapshot_id=snapshot_id,
        sandbox_id=sandbox_id,
        pipeline_run_id=body.pipeline_run_id,
        project_id=body.project_id,
        status=SandboxSnapshotStatus.COMPLETED,
        commit_sha=body.commit_sha,
        image_tag=f"snapshot-{snapshot_id[:8]}",
        ttl_seconds=body.ttl_seconds,
        created_at=now,
        expires_at=expires_at,
    )
    result: dict[str, Any] = await store.add(snapshot)
    await dispatch_event(
        request,
        SandboxSnapshotCreated(
            payload={"resource_id": snapshot_id, "sandbox_id": sandbox_id},
        ),
        stream_id=f"snapshot:{snapshot_id}",
    )
    return result


@router.get("/sandboxes/snapshots")
async def list_snapshots(
    project_id: str | None = None,
    pipeline_run_id: str | None = None,
    sandbox_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List sandbox snapshots, optionally filtered."""
    store = snapshot_store_provider.get()
    parsed_status: SandboxSnapshotStatus | None = None
    if status is not None:
        try:
            parsed_status = SandboxSnapshotStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status!r}",
            ) from None
    return await store.list_all(
        project_id=project_id,
        pipeline_run_id=pipeline_run_id,
        sandbox_id=sandbox_id,
        status=parsed_status,
    )


@router.get("/sandboxes/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Get a specific snapshot by ID."""
    store = snapshot_store_provider.get()
    result = await store.get(snapshot_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result


@router.post("/sandboxes/snapshots/{snapshot_id}/restore", status_code=201)
async def restore_snapshot(
    snapshot_id: str,
    request: Request,
) -> dict[str, Any]:
    """Restore a snapshot into a new sandbox."""
    store = snapshot_store_provider.get()
    snapshot = await store.get(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    if snapshot["status"] == SandboxSnapshotStatus.EXPIRED:
        raise HTTPException(status_code=410, detail="Snapshot has expired")

    restored_sandbox_id = f"restored-{uuid.uuid4()!s}"
    await store.update(
        snapshot_id,
        {
            "restored_sandbox_id": restored_sandbox_id,
            "status": SandboxSnapshotStatus.COMPLETED,
        },
    )

    await dispatch_event(
        request,
        SandboxSnapshotRestored(
            payload={
                "resource_id": snapshot_id,
                "restored_sandbox_id": restored_sandbox_id,
            },
        ),
        stream_id=f"snapshot:{snapshot_id}",
    )
    return {"snapshot_id": snapshot_id, "restored_sandbox_id": restored_sandbox_id}


@router.delete("/sandboxes/snapshots/{snapshot_id}", status_code=204)
async def delete_snapshot(snapshot_id: str, request: Request) -> None:
    """Delete a snapshot."""
    store = snapshot_store_provider.get()
    removed = await store.remove(snapshot_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    await dispatch_event(
        request,
        SandboxSnapshotExpired(
            payload={"resource_id": snapshot_id},
        ),
        stream_id=f"snapshot:{snapshot_id}",
    )
