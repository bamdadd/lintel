"""Tests for the repository API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestRepositoryAPI:
    def test_register_repository(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/repositories",
            json={
                "repo_id": "r1",
                "name": "my-repo",
                "url": "https://github.com/org/my-repo",
                "owner": "org",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repo_id"] == "r1"
        assert data["name"] == "my-repo"
        assert data["status"] == "active"
        assert data["default_branch"] == "main"

    def test_register_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "repo_id": "r1",
            "name": "my-repo",
            "url": "https://github.com/org/my-repo",
        }
        client.post("/api/v1/repositories", json=body)
        resp = client.post("/api/v1/repositories", json=body)
        assert resp.status_code == 409

    def test_list_repositories_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/repositories")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_repositories(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "a", "url": "https://github.com/org/a"},
        )
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r2", "name": "b", "url": "https://github.com/org/b"},
        )
        resp = client.get("/api/v1/repositories")
        assert len(resp.json()) == 2

    def test_get_repository(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "my-repo", "url": "https://github.com/org/r"},
        )
        resp = client.get("/api/v1/repositories/r1")
        assert resp.status_code == 200
        assert resp.json()["repo_id"] == "r1"

    def test_get_repository_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/repositories/nope")
        assert resp.status_code == 404

    def test_update_repository(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "old", "url": "https://github.com/org/r"},
        )
        resp = client.patch(
            "/api/v1/repositories/r1",
            json={"name": "new-name", "default_branch": "develop"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-name"
        assert data["default_branch"] == "develop"

    def test_update_repository_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client.patch(
            "/api/v1/repositories/r1",
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_update_repository_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/repositories/nope", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_repository(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client.delete("/api/v1/repositories/r1")
        assert resp.status_code == 204
        assert client.get("/api/v1/repositories/r1").status_code == 404

    def test_delete_repository_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/repositories/nope")
        assert resp.status_code == 404

    def test_partial_update_preserves_other_fields(self, client: TestClient) -> None:
        client.post(
            "/api/v1/repositories",
            json={
                "repo_id": "r1",
                "name": "repo",
                "url": "https://github.com/org/r",
                "owner": "org",
                "default_branch": "main",
            },
        )
        resp = client.patch("/api/v1/repositories/r1", json={"name": "renamed"})
        data = resp.json()
        assert data["name"] == "renamed"
        assert data["owner"] == "org"
        assert data["default_branch"] == "main"
        assert data["url"] == "https://github.com/org/r"

    def test_list_commits_repo_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/repositories/nope/commits")
        assert resp.status_code == 404

    def test_list_pull_requests_repo_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/repositories/nope/pull-requests")
        assert resp.status_code == 404


class TestRepositoryProviderEndpoints:
    """Tests for commits/PRs endpoints using a fake RepoProvider."""

    @pytest.fixture()
    def client_with_provider(self) -> Generator[TestClient]:
        from unittest.mock import AsyncMock

        from lintel.repositories_api.routes import repo_provider_provider

        app = create_app()
        with TestClient(app) as c:
            mock_provider = AsyncMock()
            mock_provider.list_commits.return_value = [
                {"sha": "abc123", "message": "init", "author": "dev", "date": "2026-01-01"},
            ]
            mock_provider.list_pull_requests.return_value = [
                {
                    "number": 1,
                    "title": "feat: add stuff",
                    "state": "open",
                    "author": "dev",
                    "created_at": "2026-01-01",
                    "updated_at": "2026-01-02",
                    "html_url": "https://github.com/org/r/pull/1",
                    "head_branch": "feature",
                    "base_branch": "main",
                },
            ]
            repo_provider_provider.override(mock_provider)
            yield c
        repo_provider_provider.override(None)

    def test_list_commits(self, client_with_provider: TestClient) -> None:
        client_with_provider.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client_with_provider.get("/api/v1/repositories/r1/commits")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sha"] == "abc123"

    def test_list_commits_custom_branch(self, client_with_provider: TestClient) -> None:
        client_with_provider.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client_with_provider.get("/api/v1/repositories/r1/commits?branch=develop&limit=5")
        assert resp.status_code == 200

    def test_list_pull_requests(self, client_with_provider: TestClient) -> None:
        client_with_provider.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client_with_provider.get("/api/v1/repositories/r1/pull-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["number"] == 1
        assert data[0]["title"] == "feat: add stuff"

    def test_list_pull_requests_closed(self, client_with_provider: TestClient) -> None:
        client_with_provider.post(
            "/api/v1/repositories",
            json={"repo_id": "r1", "name": "repo", "url": "https://github.com/org/r"},
        )
        resp = client_with_provider.get("/api/v1/repositories/r1/pull-requests?state=closed")
        assert resp.status_code == 200
