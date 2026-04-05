"""Tests for the repository create and templates endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repositories_api.routes import (
    repo_provider_provider,
    repository_store_provider,
    router,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass(frozen=True)
class FakeCreateResult:
    repo_url: str
    default_branch: str
    owner: str
    name: str


@pytest.fixture()
def client_with_provider() -> Generator[TestClient]:
    store = InMemoryRepositoryStore()
    mock_provider = AsyncMock()
    mock_provider.create_repo.return_value = FakeCreateResult(
        repo_url="https://github.com/myorg/new-repo",
        default_branch="main",
        owner="myorg",
        name="new-repo",
    )
    repository_store_provider.override(store)
    repo_provider_provider.override(mock_provider)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    repository_store_provider.override(None)
    repo_provider_provider.override(None)


class TestListTemplates:
    def test_list_templates(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.get("/api/v1/repositories/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "react-vite" in data["templates"]
        assert "python-fastapi" in data["templates"]
        assert "monorepo" in data["templates"]


class TestCreateRepository:
    def test_create_repo_without_template(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.post(
            "/api/v1/repositories/create",
            json={"name": "new-repo", "owner": "myorg"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-repo"
        assert data["url"] == "https://github.com/myorg/new-repo"
        assert data["owner"] == "myorg"
        assert data["default_branch"] == "main"
        assert data["status"] == "active"

    def test_create_repo_with_template(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.post(
            "/api/v1/repositories/create",
            json={"name": "new-repo", "owner": "myorg", "template": "react-vite"},
        )
        assert resp.status_code == 201

    def test_create_repo_with_project_ids(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.post(
            "/api/v1/repositories/create",
            json={
                "name": "new-repo",
                "owner": "myorg",
                "project_ids": ["proj-1"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["project_ids"] == ["proj-1"]

    def test_create_repo_registers_in_store(self, client_with_provider: TestClient) -> None:
        client_with_provider.post(
            "/api/v1/repositories/create",
            json={"name": "new-repo", "owner": "myorg"},
        )
        resp = client_with_provider.get("/api/v1/repositories")
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "new-repo"

    def test_create_repo_no_provider_returns_503(self) -> None:
        store = InMemoryRepositoryStore()
        repository_store_provider.override(store)
        repo_provider_provider.override(None)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as c:
            resp = c.post(
                "/api/v1/repositories/create",
                json={"name": "new-repo", "owner": "myorg"},
            )
        assert resp.status_code == 503
        repository_store_provider.override(None)
        repo_provider_provider.override(None)

    def test_create_repo_public(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.post(
            "/api/v1/repositories/create",
            json={"name": "new-repo", "owner": "myorg", "private": False},
        )
        assert resp.status_code == 201

    def test_create_repo_with_description(self, client_with_provider: TestClient) -> None:
        resp = client_with_provider.post(
            "/api/v1/repositories/create",
            json={
                "name": "new-repo",
                "owner": "myorg",
                "description": "My cool project",
            },
        )
        assert resp.status_code == 201
