"""Tests for test plan API routes."""

from fastapi.testclient import TestClient


class TestTestPlanAPI:
    def test_create_test_plan_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/test-plans",
            json={"id": "tp-1", "title": "Login tests", "project_id": "proj-1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "tp-1"
        assert data["title"] == "Login tests"
        assert data["project_id"] == "proj-1"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/test-plans", json={"id": "tp-1", "title": "Plan"})
        resp = client.post("/api/v1/test-plans", json={"id": "tp-1", "title": "Plan 2"})
        assert resp.status_code == 409

    def test_list_test_plans_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/test-plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_test_plans(self, client: TestClient) -> None:
        client.post("/api/v1/test-plans", json={"id": "tp-1", "title": "Plan 1"})
        client.post("/api/v1/test-plans", json={"id": "tp-2", "title": "Plan 2"})
        resp = client.get("/api/v1/test-plans")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_test_plan_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/test-plans",
            json={"id": "tp-1", "title": "Auth tests"},
        )
        resp = client.get("/api/v1/test-plans/tp-1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Auth tests"

    def test_get_test_plan_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/test-plans/nonexistent")
        assert resp.status_code == 404

    def test_update_test_plan(self, client: TestClient) -> None:
        client.post(
            "/api/v1/test-plans",
            json={"id": "tp-1", "title": "Old title"},
        )
        resp = client.patch(
            "/api/v1/test-plans/tp-1",
            json={"title": "New title", "description": "Updated desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New title"
        assert data["description"] == "Updated desc"

    def test_update_test_plan_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/test-plans/nonexistent",
            json={"title": "X"},
        )
        assert resp.status_code == 404

    def test_delete_test_plan(self, client: TestClient) -> None:
        client.post("/api/v1/test-plans", json={"id": "tp-1", "title": "Plan"})
        resp = client.delete("/api/v1/test-plans/tp-1")
        assert resp.status_code == 204
        assert client.get("/api/v1/test-plans/tp-1").status_code == 404

    def test_delete_test_plan_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/test-plans/nonexistent")
        assert resp.status_code == 404


class TestTestPlanWithTestCases:
    def test_create_with_test_cases(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/test-plans",
            json={
                "id": "tp-1",
                "title": "Auth tests",
                "test_cases": [
                    {
                        "id": "tc-1",
                        "name": "Login success",
                        "steps": ["Open page", "Enter creds", "Click login"],
                        "expected_result": "User logged in",
                        "priority": "high",
                    },
                    {
                        "id": "tc-2",
                        "name": "Login failure",
                        "steps": ["Open page", "Enter bad creds", "Click login"],
                        "expected_result": "Error shown",
                        "priority": "medium",
                    },
                ],
                "coverage_targets": ["auth/login", "auth/session"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["test_cases"]) == 2
        assert data["test_cases"][0]["name"] == "Login success"
        assert data["test_cases"][0]["priority"] == "high"
        assert data["test_cases"][0]["steps"] == ["Open page", "Enter creds", "Click login"]
        assert data["coverage_targets"] == ["auth/login", "auth/session"]

    def test_update_test_cases(self, client: TestClient) -> None:
        client.post(
            "/api/v1/test-plans",
            json={"id": "tp-1", "title": "Plan", "test_cases": []},
        )
        resp = client.patch(
            "/api/v1/test-plans/tp-1",
            json={
                "test_cases": [
                    {
                        "id": "tc-new",
                        "name": "New case",
                        "priority": "critical",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["test_cases"]) == 1
        assert data["test_cases"][0]["priority"] == "critical"

    def test_update_coverage_targets(self, client: TestClient) -> None:
        client.post(
            "/api/v1/test-plans",
            json={"id": "tp-1", "title": "Plan"},
        )
        resp = client.patch(
            "/api/v1/test-plans/tp-1",
            json={"coverage_targets": ["module_a", "module_b"]},
        )
        assert resp.status_code == 200
        assert resp.json()["coverage_targets"] == ["module_a", "module_b"]
