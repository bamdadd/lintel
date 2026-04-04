"""Tests for cross-repo agent API."""

from fastapi.testclient import TestClient


class TestCrossRepoAgentAPI:
    def test_create_plan_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cross-repo/plans",
            json={
                "plan_id": "p-1",
                "title": "Multi-repo refactor",
                "repositories": ["repo-a", "repo-b"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["plan_id"] == "p-1"
        assert data["title"] == "Multi-repo refactor"
        assert data["status"] == "draft"

    def test_create_duplicate_plan_returns_409(self, client: TestClient) -> None:
        body = {
            "plan_id": "p-dup",
            "title": "Dup plan",
            "repositories": ["repo-a"],
        }
        client.post("/api/v1/cross-repo/plans", json=body)
        resp = client.post("/api/v1/cross-repo/plans", json=body)
        assert resp.status_code == 409

    def test_list_plans_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cross-repo/plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_plans_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo/plans",
            json={"plan_id": "p-2", "title": "Plan 2", "repositories": ["r1"]},
        )
        resp = client.get("/api/v1/cross-repo/plans")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_plans_filter_by_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo/plans",
            json={"plan_id": "p-3", "title": "Draft", "repositories": ["r1"]},
        )
        resp = client.get("/api/v1/cross-repo/plans", params={"status": "executing"})
        assert resp.status_code == 200
        assert resp.json() == []

        resp = client.get("/api/v1/cross-repo/plans", params={"status": "draft"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_plan_returns_200(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo/plans",
            json={"plan_id": "p-4", "title": "Plan 4", "repositories": ["r1"]},
        )
        resp = client.get("/api/v1/cross-repo/plans/p-4")
        assert resp.status_code == 200
        assert resp.json()["plan_id"] == "p-4"

    def test_get_plan_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cross-repo/plans/nonexistent")
        assert resp.status_code == 404

    def test_execute_draft_plan_returns_202(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo/plans",
            json={"plan_id": "p-5", "title": "To execute", "repositories": ["r1"]},
        )
        resp = client.post("/api/v1/cross-repo/plans/p-5/execute")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "executing"
        assert data["started_at"] is not None

    def test_execute_missing_plan_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cross-repo/plans/nonexistent/execute")
        assert resp.status_code == 404

    def test_execute_already_executing_plan_returns_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo/plans",
            json={"plan_id": "p-6", "title": "Exec twice", "repositories": ["r1"]},
        )
        client.post("/api/v1/cross-repo/plans/p-6/execute")
        resp = client.post("/api/v1/cross-repo/plans/p-6/execute")
        assert resp.status_code == 409
