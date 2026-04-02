"""Tests for project engineering principles sub-resource."""

from fastapi.testclient import TestClient


def _create_project(client: TestClient, project_id: str = "p1") -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    ).json()


class TestPrinciplesCRUD:
    def test_list_principles_empty(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.get("/api/v1/projects/p1/principles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_principle(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/projects/p1/principles",
            json={
                "name": "No raw SQL",
                "description": "Always use the ORM for database access.",
                "category": "coding_standards",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "No raw SQL"
        assert data["description"] == "Always use the ORM for database access."
        assert data["category"] == "coding_standards"
        assert "principle_id" in data

    def test_list_principles_after_create(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "Principle A"},
        )
        client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "Principle B"},
        )
        resp = client.get("/api/v1/projects/p1/principles")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_principle_by_id(self, client: TestClient) -> None:
        _create_project(client)
        created = client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "Test Principle"},
        ).json()
        pid = created["principle_id"]
        resp = client.get(f"/api/v1/projects/p1/principles/{pid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Principle"

    def test_get_principle_not_found(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.get("/api/v1/projects/p1/principles/nonexistent")
        assert resp.status_code == 404

    def test_update_principle(self, client: TestClient) -> None:
        _create_project(client)
        created = client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "Old Name", "category": "general"},
        ).json()
        pid = created["principle_id"]
        resp = client.patch(
            f"/api/v1/projects/p1/principles/{pid}",
            json={"name": "New Name", "description": "Updated", "category": "review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["description"] == "Updated"
        assert data["category"] == "review"

    def test_update_principle_not_found(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.patch(
            "/api/v1/projects/p1/principles/nonexistent",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_principle(self, client: TestClient) -> None:
        _create_project(client)
        created = client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "To Delete"},
        ).json()
        pid = created["principle_id"]
        resp = client.delete(f"/api/v1/projects/p1/principles/{pid}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/projects/p1/principles/{pid}").status_code == 404

    def test_delete_principle_not_found(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.delete("/api/v1/projects/p1/principles/nonexistent")
        assert resp.status_code == 404

    def test_principles_on_missing_project_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/missing/principles")
        assert resp.status_code == 404

    def test_create_principle_default_category(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/projects/p1/principles",
            json={"name": "Simple Rule"},
        )
        assert resp.status_code == 201
        assert resp.json()["category"] == "general"
