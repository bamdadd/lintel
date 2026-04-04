"""Tests for workflow repo selector API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from lintel.workflow_repo_selector_api.routes import repo_description_store_provider, router
from lintel.workflow_repo_selector_api.store import InMemoryRepoDescriptionStore


@pytest.fixture()
def store() -> InMemoryRepoDescriptionStore:
    return InMemoryRepoDescriptionStore()


@pytest.fixture()
def app(store: InMemoryRepoDescriptionStore) -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    repo_description_store_provider.override(store)
    return application


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_register_repo_returns_201(client: AsyncClient) -> None:
    resp = await client.post(
        "/workflow-repo-selector/repos",
        json={"name": "my-repo", "project_id": "p1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-repo"
    assert data["project_id"] == "p1"
    assert "repo_id" in data


async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    body = {"repo_id": "dup", "name": "dup-repo"}
    resp = await client.post("/workflow-repo-selector/repos", json=body)
    assert resp.status_code == 201
    resp2 = await client.post("/workflow-repo-selector/repos", json=body)
    assert resp2.status_code == 409


async def test_list_empty_returns_empty(client: AsyncClient) -> None:
    resp = await client.get("/workflow-repo-selector/repos")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_returns_registered(client: AsyncClient) -> None:
    await client.post("/workflow-repo-selector/repos", json={"name": "r1"})
    resp = await client.get("/workflow-repo-selector/repos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_filter_by_project_id(client: AsyncClient) -> None:
    await client.post("/workflow-repo-selector/repos", json={"name": "a", "project_id": "p1"})
    await client.post("/workflow-repo-selector/repos", json={"name": "b", "project_id": "p2"})
    resp = await client.get("/workflow-repo-selector/repos", params={"project_id": "p1"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["project_id"] == "p1"


async def test_delete_existing_returns_204(client: AsyncClient) -> None:
    resp = await client.post("/workflow-repo-selector/repos", json={"repo_id": "del1", "name": "x"})
    assert resp.status_code == 201
    resp2 = await client.delete("/workflow-repo-selector/repos/del1")
    assert resp2.status_code == 204


async def test_delete_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.delete("/workflow-repo-selector/repos/nonexistent")
    assert resp.status_code == 404


async def test_select_matching_repos(client: AsyncClient) -> None:
    await client.post(
        "/workflow-repo-selector/repos",
        json={
            "name": "backend-api",
            "description": "REST API for user management",
            "tags": ["python", "fastapi"],
            "languages": ["python"],
        },
    )
    resp = await client.post(
        "/workflow-repo-selector/select",
        json={"description": "fix python API endpoint"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["selections"]) >= 1
    assert data["selections"][0]["name"] == "backend-api"
    assert data["selections"][0]["score"] > 0


async def test_select_no_matching_repos(client: AsyncClient) -> None:
    await client.post(
        "/workflow-repo-selector/repos",
        json={"name": "frontend", "description": "React UI", "tags": ["react"]},
    )
    resp = await client.post(
        "/workflow-repo-selector/select",
        json={"description": "deploy kubernetes cluster"},
    )
    assert resp.status_code == 200
    assert resp.json()["selections"] == []
