"""Tests for repo auto-describe API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.repo_auto_describe_api.routes import repo_description_store_provider, router
from lintel.repo_auto_describe_api.store import InMemoryRepoDescriptionStore

if TYPE_CHECKING:
    from collections.abc import Generator

BASE = "/api/v1"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    store = InMemoryRepoDescriptionStore()
    repo_description_store_provider.override(store)
    with TestClient(app) as c:
        yield c
    repo_description_store_provider.reset()


class TestAutoDescribe:
    def test_trigger_returns_201(self, client: TestClient) -> None:
        resp = client.post(f"{BASE}/repositories/repo-1/auto-describe")
        assert resp.status_code == 201
        data = resp.json()
        assert data["repo_id"] == "repo-1"
        assert data["status"] == "completed"
        assert data["summary"] != ""
        assert len(data["languages"]) > 0
        assert len(data["frameworks"]) > 0
        assert len(data["topics"]) > 0
        assert data["completed_at"] != ""

    def test_get_latest_description(self, client: TestClient) -> None:
        client.post(f"{BASE}/repositories/repo-1/auto-describe")
        resp = client.get(f"{BASE}/repositories/repo-1/auto-describe")
        assert resp.status_code == 200
        assert resp.json()["repo_id"] == "repo-1"

    def test_get_description_not_found(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/repositories/missing/auto-describe")
        assert resp.status_code == 404

    def test_get_by_id(self, client: TestClient) -> None:
        resp = client.post(f"{BASE}/repositories/repo-1/auto-describe")
        desc_id = resp.json()["id"]
        resp = client.get(f"{BASE}/repositories/auto-describe/{desc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == desc_id

    def test_get_by_id_not_found(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/repositories/auto-describe/missing")
        assert resp.status_code == 404

    def test_list_descriptions_empty(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/repositories/auto-describe")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_descriptions_after_trigger(self, client: TestClient) -> None:
        client.post(f"{BASE}/repositories/repo-1/auto-describe")
        client.post(f"{BASE}/repositories/repo-2/auto-describe")
        resp = client.get(f"{BASE}/repositories/auto-describe")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_multiple_triggers_same_repo(self, client: TestClient) -> None:
        client.post(f"{BASE}/repositories/repo-1/auto-describe")
        resp2 = client.post(f"{BASE}/repositories/repo-1/auto-describe")
        # GET returns latest
        resp = client.get(f"{BASE}/repositories/repo-1/auto-describe")
        assert resp.status_code == 200
        assert resp.json()["id"] == resp2.json()["id"]


class TestStoreOperations:
    """Direct store tests."""

    @pytest.fixture()
    def store(self) -> InMemoryRepoDescriptionStore:
        return InMemoryRepoDescriptionStore()

    async def test_get_by_repo_missing(self, store: InMemoryRepoDescriptionStore) -> None:
        result = await store.get_by_repo("nonexistent")
        assert result is None

    async def test_add_and_get(self, store: InMemoryRepoDescriptionStore) -> None:
        from lintel.repo_auto_describe_api.types import RepoDescription

        desc = RepoDescription(id="d1", repo_id="r1", summary="test")
        await store.add(desc)
        result = await store.get("d1")
        assert result is not None
        assert result.summary == "test"

    async def test_list_all(self, store: InMemoryRepoDescriptionStore) -> None:
        from lintel.repo_auto_describe_api.types import RepoDescription

        await store.add(RepoDescription(id="d1", repo_id="r1"))
        await store.add(RepoDescription(id="d2", repo_id="r2"))
        result = await store.list_all()
        assert len(result) == 2
