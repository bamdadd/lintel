"""Tests for cross-repo test API."""

from fastapi.testclient import TestClient


class TestCrossRepoTestAPI:
    def test_create_run_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cross-repo-tests/runs",
            json={
                "run_id": "run-1",
                "repositories": ["repo-a", "repo-b"],
                "project_id": "proj-1",
                "triggered_by": "user-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == "run-1"
        assert data["repositories"] == ["repo-a", "repo-b"]
        assert data["status"] == "pending"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "run_id": "run-dup",
            "repositories": ["repo-a"],
        }
        client.post("/api/v1/cross-repo-tests/runs", json=body)
        resp = client.post("/api/v1/cross-repo-tests/runs", json=body)
        assert resp.status_code == 409

    def test_list_empty_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cross-repo-tests/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo-tests/runs",
            json={"run_id": "run-2", "repositories": ["repo-a"]},
        )
        resp = client.get("/api/v1/cross-repo-tests/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["run_id"] == "run-2"

    def test_list_filter_by_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo-tests/runs",
            json={"run_id": "run-a", "repositories": ["repo-a"]},
        )
        client.post(
            "/api/v1/cross-repo-tests/runs",
            json={"run_id": "run-b", "repositories": ["repo-b"]},
        )
        resp = client.get("/api/v1/cross-repo-tests/runs", params={"status": "pending"})
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get("/api/v1/cross-repo-tests/runs", params={"status": "running"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_get_existing_returns_200(self, client: TestClient) -> None:
        client.post(
            "/api/v1/cross-repo-tests/runs",
            json={"run_id": "run-3", "repositories": ["repo-a"]},
        )
        resp = client.get("/api/v1/cross-repo-tests/runs/run-3")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run-3"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cross-repo-tests/runs/nonexistent")
        assert resp.status_code == 404
