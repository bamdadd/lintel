"""Tests for integration patterns API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore


class TestIntegrationPatternsAPI:
    def test_create_integration_map_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repository_id"] == "repo-1"
        assert data["workflow_run_id"] == "run-1"
        assert data["status"] == "pending"
        assert "map_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_list_integration_maps_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/integration-maps")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_integration_maps_with_data(self, client: TestClient) -> None:
        client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-2", "workflow_run_id": "run-2"},
        )
        resp = client.get("/api/v1/integration-maps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # Filter by repository_id
        resp_filtered = client.get("/api/v1/integration-maps?repository_id=repo-1")
        assert resp_filtered.status_code == 200
        filtered = resp_filtered.json()
        assert len(filtered) == 1
        assert filtered[0]["repository_id"] == "repo-1"

    def test_get_integration_map_found(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        map_id = create_resp.json()["map_id"]

        resp = client.get(f"/api/v1/integration-maps/{map_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["map_id"] == map_id
        assert data["repository_id"] == "repo-1"

    def test_get_integration_map_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/integration-maps/nonexistent")
        assert resp.status_code == 404

    def test_get_graph_empty(
        self, client: TestClient, store: InMemoryIntegrationPatternStore
    ) -> None:
        create_resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        map_id = create_resp.json()["map_id"]

        resp = client.get(f"/api/v1/integration-maps/{map_id}/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["map_id"] == map_id
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_get_patterns_empty(
        self, client: TestClient, store: InMemoryIntegrationPatternStore
    ) -> None:
        create_resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        map_id = create_resp.json()["map_id"]

        resp = client.get(f"/api/v1/integration-maps/{map_id}/patterns")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_antipatterns_empty(
        self, client: TestClient, store: InMemoryIntegrationPatternStore
    ) -> None:
        create_resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        map_id = create_resp.json()["map_id"]

        resp = client.get(f"/api/v1/integration-maps/{map_id}/antipatterns")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_coupling_scores_empty(
        self, client: TestClient, store: InMemoryIntegrationPatternStore
    ) -> None:
        create_resp = client.post(
            "/api/v1/integration-maps",
            json={"repository_id": "repo-1", "workflow_run_id": "run-1"},
        )
        map_id = create_resp.json()["map_id"]

        resp = client.get(f"/api/v1/integration-maps/{map_id}/coupling-scores")
        assert resp.status_code == 200
        assert resp.json() == []
