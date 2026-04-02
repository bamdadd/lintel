"""Tests for codebase index API endpoints."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


# ======================== Indices ========================


class TestCodebaseIndexAPI:
    def test_create_index(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/codebase-indices",
            json={
                "index_id": "idx-1",
                "project_id": "proj-1",
                "repository_url": "https://github.com/org/repo",
                "branch": "main",
                "name": "My Repo Index",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["index_id"] == "idx-1"
        assert data["repository_url"] == "https://github.com/org/repo"
        assert data["status"] == "pending"

    def test_create_index_duplicate(self, client: TestClient) -> None:
        _create_project(client)
        payload = {
            "index_id": "idx-dup",
            "project_id": "proj-1",
            "repository_url": "https://github.com/org/repo",
        }
        client.post("/api/v1/codebase-indices", json=payload)
        resp = client.post("/api/v1/codebase-indices", json=payload)
        assert resp.status_code == 409

    def test_list_indices(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-a", "project_id": "proj-1", "repository_url": "u1"},
        )
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-b", "project_id": "proj-1", "repository_url": "u2"},
        )
        resp = client.get("/api/v1/codebase-indices")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_indices_by_project(self, client: TestClient) -> None:
        _create_project(client, "proj-a")
        _create_project(client, "proj-b")
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-pa", "project_id": "proj-a", "repository_url": "u1"},
        )
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-pb", "project_id": "proj-b", "repository_url": "u2"},
        )
        resp = client.get("/api/v1/codebase-indices", params={"project_id": "proj-a"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-a"

    def test_get_index(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-get", "project_id": "proj-1", "repository_url": "u"},
        )
        resp = client.get("/api/v1/codebase-indices/idx-get")
        assert resp.status_code == 200
        assert resp.json()["index_id"] == "idx-get"

    def test_get_index_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/codebase-indices/nonexistent")
        assert resp.status_code == 404

    def test_update_index(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-upd", "project_id": "proj-1", "repository_url": "u"},
        )
        resp = client.patch(
            "/api/v1/codebase-indices/idx-upd",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_delete_index(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-del", "project_id": "proj-1", "repository_url": "u"},
        )
        resp = client.delete("/api/v1/codebase-indices/idx-del")
        assert resp.status_code == 204
        assert client.get("/api/v1/codebase-indices/idx-del").status_code == 404


# ======================== Entries ========================


class TestCodebaseEntryAPI:
    def test_create_entry(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-e1", "project_id": "proj-1", "repository_url": "u"},
        )
        resp = client.post(
            "/api/v1/codebase-indices/idx-e1/entries",
            json={
                "entry_id": "ent-1",
                "file_path": "src/main.py",
                "content": "def hello(): pass",
                "language": "python",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["file_path"] == "src/main.py"

    def test_list_entries(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-e2", "project_id": "proj-1", "repository_url": "u"},
        )
        client.post(
            "/api/v1/codebase-indices/idx-e2/entries",
            json={"entry_id": "ent-a", "file_path": "a.py", "content": "aaa"},
        )
        client.post(
            "/api/v1/codebase-indices/idx-e2/entries",
            json={"entry_id": "ent-b", "file_path": "b.py", "content": "bbb"},
        )
        resp = client.get("/api/v1/codebase-indices/idx-e2/entries")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_create_entry_index_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/codebase-indices/nonexistent/entries",
            json={"entry_id": "ent-x", "file_path": "x.py"},
        )
        assert resp.status_code == 404


# ======================== Search ========================


class TestCodebaseSearchAPI:
    def test_search(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-s1", "project_id": "proj-1", "repository_url": "u"},
        )
        client.post(
            "/api/v1/codebase-indices/idx-s1/entries",
            json={"entry_id": "ent-s1", "file_path": "main.py", "content": "def authenticate():"},
        )
        client.post(
            "/api/v1/codebase-indices/idx-s1/entries",
            json={"entry_id": "ent-s2", "file_path": "utils.py", "content": "def helper():"},
        )
        resp = client.get("/api/v1/codebase-indices/idx-s1/search", params={"q": "authenticate"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["file_path"] == "main.py"

    def test_search_index_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/codebase-indices/nonexistent/search", params={"q": "foo"})
        assert resp.status_code == 404


# ======================== Reindex ========================


class TestReindexAPI:
    def test_trigger_reindex(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/codebase-indices",
            json={"index_id": "idx-r1", "project_id": "proj-1", "repository_url": "u"},
        )
        resp = client.post(
            "/api/v1/codebase-indices/idx-r1/reindex",
            json={"commit_sha": "abc123"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "reindex_triggered"
        # Verify status updated
        idx = client.get("/api/v1/codebase-indices/idx-r1").json()
        assert idx["status"] == "indexing"
        assert idx["last_commit_sha"] == "abc123"

    def test_trigger_reindex_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/codebase-indices/nonexistent/reindex", json={})
        assert resp.status_code == 404
