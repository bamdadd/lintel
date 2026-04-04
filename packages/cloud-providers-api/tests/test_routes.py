"""Tests for cloud providers API routes."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from lintel.cloud_providers_api.routes import cloud_provider_store_provider, router
from lintel.cloud_providers_api.store import InMemoryCloudProviderStore


@pytest.fixture()
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture(autouse=True)
def _wire_store() -> None:
    store = InMemoryCloudProviderStore()
    cloud_provider_store_provider.override(store)


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_create_cloud_provider(client: AsyncClient) -> None:
    resp = await client.post(
        "/cloud-providers",
        json={"name": "My AWS", "provider_type": "aws", "credentials_id": "cred-1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My AWS"
    assert data["provider_type"] == "aws"
    assert data["credentials_id"] == "cred-1"
    assert "id" in data


async def test_list_cloud_providers(client: AsyncClient) -> None:
    await client.post("/cloud-providers", json={"name": "AWS", "provider_type": "aws"})
    await client.post("/cloud-providers", json={"name": "GCP", "provider_type": "gcp"})
    resp = await client.get("/cloud-providers")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_cloud_provider(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/cloud-providers",
        json={"name": "Azure", "provider_type": "azure"},
    )
    provider_id = create_resp.json()["id"]
    resp = await client.get(f"/cloud-providers/{provider_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Azure"
    assert resp.json()["provider_type"] == "azure"


async def test_get_cloud_provider_not_found(client: AsyncClient) -> None:
    resp = await client.get("/cloud-providers/nonexistent")
    assert resp.status_code == 404


async def test_delete_cloud_provider(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/cloud-providers",
        json={"name": "To Delete", "provider_type": "gcp"},
    )
    provider_id = create_resp.json()["id"]
    resp = await client.delete(f"/cloud-providers/{provider_id}")
    assert resp.status_code == 204
    # Verify deleted
    get_resp = await client.get(f"/cloud-providers/{provider_id}")
    assert get_resp.status_code == 404


async def test_delete_cloud_provider_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/cloud-providers/nonexistent")
    assert resp.status_code == 404


async def test_create_with_config(client: AsyncClient) -> None:
    resp = await client.post(
        "/cloud-providers",
        json={
            "name": "Configured AWS",
            "provider_type": "aws",
            "config": {"region": "us-east-1"},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["config"] == {"region": "us-east-1"}


# --- Store unit tests ---


async def test_store_add_and_get() -> None:
    from lintel.cloud_providers_api.types import CloudProvider

    store = InMemoryCloudProviderStore()
    provider = CloudProvider(id="p1", name="Test", provider_type="aws")
    await store.add(provider)
    result = await store.get("p1")
    assert result is not None
    assert result.name == "Test"


async def test_store_delete() -> None:
    from lintel.cloud_providers_api.types import CloudProvider

    store = InMemoryCloudProviderStore()
    provider = CloudProvider(id="p1", name="Test", provider_type="aws")
    await store.add(provider)
    assert await store.delete("p1") is True
    assert await store.get("p1") is None
    assert await store.delete("p1") is False
