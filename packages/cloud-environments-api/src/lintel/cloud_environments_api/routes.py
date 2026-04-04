"""Cloud environment provisioning endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.cloud_environments_api.types import (
    CloudEnvironment,
    CloudEnvStatus,
    CloudProvider,
)

if TYPE_CHECKING:
    from lintel.cloud_environments_api.store import InMemoryCloudEnvironmentStore
    from lintel.contracts.events import EventEnvelope

router = APIRouter()

cloud_environment_store_provider: StoreProvider[InMemoryCloudEnvironmentStore] = StoreProvider()


class ProvisionRequest(BaseModel):
    cloud_environment_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    provider: CloudProvider
    instance_type: str = "t3.micro"
    region: str = "us-east-1"
    config: dict[str, object] | None = None


class DestroyRequest(BaseModel):
    force: bool = False


@router.post("/cloud-environments/provision", status_code=201)
async def provision_cloud_environment(
    body: ProvisionRequest,
    request: Request,
    store: InMemoryCloudEnvironmentStore = Depends(cloud_environment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Provision a new cloud VM environment (stub)."""
    existing = await store.get(body.cloud_environment_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Cloud environment already exists")
    env = CloudEnvironment(
        cloud_environment_id=body.cloud_environment_id,
        name=body.name,
        provider=body.provider,
        instance_type=body.instance_type,
        region=body.region,
        status=CloudEnvStatus.PROVISIONING,
        config=body.config,
    )
    await store.add(env)
    await dispatch_event(
        request,
        _make_event("CloudEnvironmentProvisioned", env.cloud_environment_id),
        stream_id=f"cloud-environment:{env.cloud_environment_id}",
    )
    return asdict(env)


@router.post("/cloud-environments/{cloud_environment_id}/destroy", status_code=200)
async def destroy_cloud_environment(
    cloud_environment_id: str,
    body: DestroyRequest,
    request: Request,
    store: InMemoryCloudEnvironmentStore = Depends(cloud_environment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Destroy a cloud VM environment (stub)."""
    env = await store.get(cloud_environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Cloud environment not found")
    if env.status == CloudEnvStatus.DESTROYED:
        raise HTTPException(status_code=409, detail="Cloud environment already destroyed")
    now = datetime.now(UTC).isoformat()
    updated = CloudEnvironment(
        **{**asdict(env), "status": CloudEnvStatus.DESTROYING, "updated_at": now},
    )
    await store.update(updated)
    await dispatch_event(
        request,
        _make_event("CloudEnvironmentDestroying", cloud_environment_id),
        stream_id=f"cloud-environment:{cloud_environment_id}",
    )
    return asdict(updated)


@router.get("/cloud-environments")
async def list_cloud_environments(
    store: InMemoryCloudEnvironmentStore = Depends(cloud_environment_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all cloud environments."""
    envs = await store.list_all()
    return [asdict(e) for e in envs]


@router.get("/cloud-environments/{cloud_environment_id}")
async def get_cloud_environment(
    cloud_environment_id: str,
    store: InMemoryCloudEnvironmentStore = Depends(cloud_environment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get status of a cloud environment."""
    env = await store.get(cloud_environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Cloud environment not found")
    return asdict(env)


def _make_event(event_type: str, resource_id: str) -> EventEnvelope:
    """Create a lightweight event payload for dispatch."""
    from lintel.contracts.events import EventEnvelope

    return EventEnvelope(
        event_type=event_type,
        payload={"resource_id": resource_id},
    )
