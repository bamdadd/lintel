"""Cloud providers API endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.cloud_providers_api.store import InMemoryCloudProviderStore

router = APIRouter()

cloud_provider_store_provider: StoreProvider[InMemoryCloudProviderStore] = StoreProvider()


@router.post("/cloud-providers", status_code=201)
async def create_cloud_provider(
    body: dict[str, Any],
    store: InMemoryCloudProviderStore = Depends(cloud_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a new cloud provider configuration."""
    from lintel.cloud_providers_api.types import CloudProvider

    provider = CloudProvider(
        id=str(uuid4()),
        name=body.get("name", ""),
        provider_type=body.get("provider_type", "aws"),
        config=body.get("config", {}),
        credentials_id=body.get("credentials_id", ""),
    )
    await store.add(provider)
    return asdict(provider)


@router.get("/cloud-providers")
async def list_cloud_providers(
    store: InMemoryCloudProviderStore = Depends(cloud_provider_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all cloud providers."""
    providers = await store.list_all()
    return [asdict(p) for p in providers]


@router.get("/cloud-providers/{provider_id}")
async def get_cloud_provider(
    provider_id: str,
    store: InMemoryCloudProviderStore = Depends(cloud_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a cloud provider by ID."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Cloud provider not found")
    return asdict(provider)


@router.delete("/cloud-providers/{provider_id}", status_code=204)
async def delete_cloud_provider(
    provider_id: str,
    store: InMemoryCloudProviderStore = Depends(cloud_provider_store_provider),  # noqa: B008
) -> None:
    """Delete a cloud provider."""
    deleted = await store.delete(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cloud provider not found")
