"""Tests for tech spec API."""

from fastapi.testclient import TestClient


class TestTechSpecAPI:
    def test_create_tech_spec_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/tech-specs",
            json={
                "id": "ts-1",
                "project_id": "proj-1",
                "title": "Add caching layer",
                "problem_statement": "API is slow",
                "proposed_solution": "Add Redis cache",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "ts-1"
        assert data["title"] == "Add caching layer"
        assert data["status"] == "draft"
        assert data["project_id"] == "proj-1"

    def test_create_tech_spec_conflict(self, client: TestClient) -> None:
        payload = {"id": "ts-dup", "project_id": "p1", "title": "Dup"}
        client.post("/api/v1/tech-specs", json=payload)
        resp = client.post("/api/v1/tech-specs", json=payload)
        assert resp.status_code == 409

    def test_list_tech_specs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tech-specs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tech_specs_filter_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-a", "project_id": "p1", "title": "A"},
        )
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-b", "project_id": "p2", "title": "B"},
        )
        resp = client.get("/api/v1/tech-specs", params={"project_id": "p1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "ts-a"

    def test_get_tech_spec_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-2", "project_id": "p1", "title": "Spec"},
        )
        resp = client.get("/api/v1/tech-specs/ts-2")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Spec"

    def test_get_tech_spec_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tech-specs/nonexistent")
        assert resp.status_code == 404

    def test_update_tech_spec(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-3", "project_id": "p1", "title": "Old title"},
        )
        resp = client.patch(
            "/api/v1/tech-specs/ts-3",
            json={"title": "New title", "status": "review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New title"
        assert data["status"] == "review"

    def test_update_tech_spec_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/tech-specs/nope",
            json={"title": "X"},
        )
        assert resp.status_code == 404

    def test_delete_tech_spec_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-4", "project_id": "p1", "title": "To delete"},
        )
        resp = client.delete("/api/v1/tech-specs/ts-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/tech-specs/ts-4").status_code == 404

    def test_delete_tech_spec_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/tech-specs/nonexistent")
        assert resp.status_code == 404


class TestTechSpecMilestones:
    def test_create_with_milestones(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/tech-specs",
            json={
                "id": "ts-m1",
                "project_id": "p1",
                "title": "With milestones",
                "milestones": [
                    {
                        "name": "Phase 1",
                        "description": "Initial setup",
                        "estimated_effort": "2 weeks",
                    },
                    {"name": "Phase 2", "description": "Implementation"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["milestones"]) == 2
        assert data["milestones"][0]["name"] == "Phase 1"
        assert data["milestones"][0]["estimated_effort"] == "2 weeks"

    def test_update_milestones(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-m2", "project_id": "p1", "title": "Spec"},
        )
        resp = client.patch(
            "/api/v1/tech-specs/ts-m2",
            json={"milestones": [{"name": "M1", "description": "First", "estimated_effort": "1d"}]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["milestones"]) == 1


class TestTechSpecListFields:
    def test_create_with_list_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/tech-specs",
            json={
                "id": "ts-l1",
                "project_id": "p1",
                "title": "Lists",
                "alternatives": ["Option A", "Option B"],
                "dependencies": ["dep-1"],
                "risks": ["Risk 1", "Risk 2"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["alternatives"] == ["Option A", "Option B"]
        assert data["dependencies"] == ["dep-1"]
        assert data["risks"] == ["Risk 1", "Risk 2"]

    def test_update_list_fields(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tech-specs",
            json={"id": "ts-l2", "project_id": "p1", "title": "Spec"},
        )
        resp = client.patch(
            "/api/v1/tech-specs/ts-l2",
            json={"alternatives": ["New option"], "risks": ["New risk"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alternatives"] == ["New option"]
        assert data["risks"] == ["New risk"]
