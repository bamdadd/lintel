"""Tests for frontend-targets-api routes."""

from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from lintel.frontend_targets_api.routes import frontend_target_store_provider, router
from lintel.frontend_targets_api.store import InMemoryFrontendTargetStore


@pytest.fixture()
def store() -> InMemoryFrontendTargetStore:
    return InMemoryFrontendTargetStore()


@pytest.fixture()
def app(store: InMemoryFrontendTargetStore) -> FastAPI:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    frontend_target_store_provider.override(store)
    application.state.event_bus = AsyncMock()
    application.state.event_store = AsyncMock()
    application.state.event_store.append = AsyncMock()
    yield application  # type: ignore[misc]
    frontend_target_store_provider.reset()


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def test_create_frontend_target(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "web", "label": "Main Web App"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == "proj-1"
    assert data["platform"] == "web"
    assert data["label"] == "Main Web App"
    assert "target_id" in data


async def test_create_invalid_platform(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "gameboy"},
    )
    assert resp.status_code == 422


async def test_create_duplicate(client: AsyncClient) -> None:
    body = {"target_id": "t-1", "project_id": "proj-1", "platform": "ios"}
    await client.post("/api/v1/frontend-targets", json=body)
    resp = await client.post("/api/v1/frontend-targets", json=body)
    assert resp.status_code == 409


async def test_list_frontend_targets(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "web"},
    )
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "ios"},
    )
    resp = await client.get("/api/v1/frontend-targets")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_filter_by_project(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "web"},
    )
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-2", "platform": "android"},
    )
    resp = await client.get("/api/v1/frontend-targets", params={"project_id": "proj-1"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["project_id"] == "proj-1"


async def test_list_filter_by_platform(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "web"},
    )
    await client.post(
        "/api/v1/frontend-targets",
        json={"project_id": "proj-1", "platform": "ios"},
    )
    resp = await client.get("/api/v1/frontend-targets", params={"platform": "ios"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["platform"] == "ios"


async def test_get_frontend_target(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"target_id": "t-1", "project_id": "proj-1", "platform": "electron"},
    )
    resp = await client.get("/api/v1/frontend-targets/t-1")
    assert resp.status_code == 200
    assert resp.json()["platform"] == "electron"


async def test_get_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/frontend-targets/missing")
    assert resp.status_code == 404


async def test_update_frontend_target(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"target_id": "t-1", "project_id": "proj-1", "platform": "web"},
    )
    resp = await client.patch(
        "/api/v1/frontend-targets/t-1",
        json={"label": "Updated Label", "platform": "ios"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated Label"
    assert resp.json()["platform"] == "ios"


async def test_update_invalid_platform(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"target_id": "t-1", "project_id": "proj-1", "platform": "web"},
    )
    resp = await client.patch(
        "/api/v1/frontend-targets/t-1",
        json={"platform": "gameboy"},
    )
    assert resp.status_code == 422


async def test_update_not_found(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/frontend-targets/missing",
        json={"label": "x"},
    )
    assert resp.status_code == 404


async def test_delete_frontend_target(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/frontend-targets",
        json={"target_id": "t-1", "project_id": "proj-1", "platform": "web"},
    )
    resp = await client.delete("/api/v1/frontend-targets/t-1")
    assert resp.status_code == 204
    resp = await client.get("/api/v1/frontend-targets/t-1")
    assert resp.status_code == 404


async def test_delete_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/frontend-targets/missing")
    assert resp.status_code == 404
