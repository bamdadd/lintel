"""Tests for fleet execution API."""

from fastapi.testclient import TestClient


class TestFleetRunCRUD:
    def test_create_fleet_run_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/fleet/runs",
            json={
                "run_id": "fr-1",
                "name": "Update deps",
                "repo_ids": ["repo-a", "repo-b", "repo-c"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == "fr-1"
        assert data["name"] == "Update deps"
        assert data["status"] == "running"
        assert len(data["repo_runs"]) == 3
        assert data["repo_runs"][0]["status"] == "pending"

    def test_create_fleet_run_empty_repos_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/fleet/runs",
            json={"name": "Empty", "repo_ids": []},
        )
        assert resp.status_code == 422

    def test_create_fleet_run_duplicate_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-dup", "name": "First", "repo_ids": ["r1"]},
        )
        resp = client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-dup", "name": "Second", "repo_ids": ["r2"]},
        )
        assert resp.status_code == 409

    def test_list_fleet_runs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/fleet/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_fleet_runs_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-2", "name": "Run A", "repo_ids": ["r1"]},
        )
        resp = client.get("/api/v1/fleet/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_fleet_run_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-3", "name": "Run B", "repo_ids": ["r1", "r2"]},
        )
        resp = client.get("/api/v1/fleet/runs/fr-3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Run B"
        assert len(data["repo_runs"]) == 2

    def test_get_fleet_run_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/fleet/runs/nonexistent")
        assert resp.status_code == 404


class TestFleetRunCancel:
    def test_cancel_running_fleet_run(self, client: TestClient) -> None:
        client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-4", "name": "Cancellable", "repo_ids": ["r1"]},
        )
        resp = client.post("/api/v1/fleet/runs/fr-4/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["cancelled_at"] != ""

    def test_cancel_already_cancelled_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/fleet/runs",
            json={"run_id": "fr-5", "name": "Double cancel", "repo_ids": ["r1"]},
        )
        client.post("/api/v1/fleet/runs/fr-5/cancel")
        resp = client.post("/api/v1/fleet/runs/fr-5/cancel")
        assert resp.status_code == 409

    def test_cancel_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/fleet/runs/nonexistent/cancel")
        assert resp.status_code == 404
