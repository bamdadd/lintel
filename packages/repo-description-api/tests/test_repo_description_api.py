"""Tests for repo-description-api routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from lintel.repo_description_api.routes import repo_description_store_provider, router
from lintel.repo_description_api.store import InMemoryRepoDescriptionStore


@pytest.fixture()
def store() -> InMemoryRepoDescriptionStore:
    return InMemoryRepoDescriptionStore()


@pytest.fixture()
def app(store: InMemoryRepoDescriptionStore) -> FastAPI:  # type: ignore[misc]
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    repo_description_store_provider.override(store)
    application.state.event_bus = AsyncMock()
    application.state.event_store = AsyncMock()
    application.state.event_store.append = AsyncMock()
    yield application  # type: ignore[misc]
    repo_description_store_provider.reset()


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def test_put_description(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "Main backend service"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "proj-1"
    assert data["repo_id"] == "repo-1"
    assert data["description"] == "Main backend service"


async def test_put_description_overwrites(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "Old"},
    )
    resp = await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "New"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "New"


async def test_get_description(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "A repo"},
    )
    resp = await client.get(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "A repo"


async def test_get_description_not_found(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/projects/proj-1/repositories/missing/description",
    )
    assert resp.status_code == 404


async def test_list_descriptions(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "First"},
    )
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-2/description",
        json={"description": "Second"},
    )
    resp = await client.get("/api/v1/projects/proj-1/repo-descriptions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    ids = {i["repo_id"] for i in items}
    assert ids == {"repo-1", "repo-2"}


async def test_list_descriptions_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/projects/proj-99/repo-descriptions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_descriptions_scoped_by_project(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "Proj 1"},
    )
    await client.put(
        "/api/v1/projects/proj-2/repositories/repo-2/description",
        json={"description": "Proj 2"},
    )
    resp = await client.get("/api/v1/projects/proj-1/repo-descriptions")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["project_id"] == "proj-1"


async def test_delete_description(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
        json={"description": "To delete"},
    )
    resp = await client.delete(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
    )
    assert resp.status_code == 204
    resp = await client.get(
        "/api/v1/projects/proj-1/repositories/repo-1/description",
    )
    assert resp.status_code == 404


async def test_delete_description_not_found(client: AsyncClient) -> None:
    resp = await client.delete(
        "/api/v1/projects/proj-1/repositories/missing/description",
    )
    assert resp.status_code == 404
