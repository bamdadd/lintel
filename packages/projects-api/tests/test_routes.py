"""Tests for projects API."""

from fastapi.testclient import TestClient


def _create_project(client: TestClient, project_id: str = "p1") -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/projects",
        json={
            "project_id": project_id,
            "name": "Test Project",
            "repo_ids": ["repo-1"],
        },
    ).json()


class TestProjectsAPI:
    def test_create_project(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={
                "project_id": "p1",
                "name": "My Project",
                "repo_ids": ["repo-1", "repo-2"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == "p1"
        assert data["name"] == "My Project"
        assert data["repo_ids"] == ["repo-1", "repo-2"]
        assert data["default_branch"] == "main"
        assert data["credential_ids"] == []

    def test_create_project_no_repos(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={"project_id": "p-empty", "name": "Empty"},
        )
        assert resp.status_code == 201
        assert resp.json()["repo_ids"] == []

    def test_create_project_duplicate_returns_409(self, client: TestClient) -> None:
        _create_project(client, "dup")
        resp = client.post(
            "/api/v1/projects",
            json={"project_id": "dup", "name": "Again"},
        )
        assert resp.status_code == 409

    def test_list_projects_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_projects_with_items(self, client: TestClient) -> None:
        _create_project(client, "a")
        _create_project(client, "b")
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_project_by_id(self, client: TestClient) -> None:
        _create_project(client, "p1")
        resp = client.get("/api/v1/projects/p1")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "p1"

    def test_get_project_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/missing")
        assert resp.status_code == 404

    def test_update_project(self, client: TestClient) -> None:
        _create_project(client, "p1")
        resp = client.patch(
            "/api/v1/projects/p1",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["project_id"] == "p1"

    def test_update_project_repo_ids(self, client: TestClient) -> None:
        _create_project(client, "p1")
        resp = client.patch(
            "/api/v1/projects/p1",
            json={"repo_ids": ["repo-a", "repo-b", "repo-c"]},
        )
        assert resp.status_code == 200
        assert resp.json()["repo_ids"] == ["repo-a", "repo-b", "repo-c"]

    def test_delete_project(self, client: TestClient) -> None:
        _create_project(client, "p1")
        resp = client.delete("/api/v1/projects/p1")
        assert resp.status_code == 204
        assert client.get("/api/v1/projects/p1").status_code == 404
