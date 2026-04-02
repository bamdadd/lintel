"""Tests for observations API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestObservationsAPI:
    def test_create_observation_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/observations",
            json={
                "observation_id": "obs-1",
                "run_id": "run-1",
                "project_id": "proj-1",
                "content": "Model accuracy improved by 5%",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["observation_id"] == "obs-1"
        assert data["content"] == "Model accuracy improved by 5%"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "observation_id": "obs-dup",
            "run_id": "run-1",
            "project_id": "proj-1",
            "content": "test",
        }
        client.post("/api/v1/observations", json=payload)
        resp = client.post("/api/v1/observations", json=payload)
        assert resp.status_code == 409

    def test_get_observation(self, client: TestClient) -> None:
        client.post(
            "/api/v1/observations",
            json={
                "observation_id": "obs-get",
                "run_id": "run-1",
                "project_id": "proj-1",
                "content": "test",
            },
        )
        resp = client.get("/api/v1/observations/obs-get")
        assert resp.status_code == 200
        assert resp.json()["observation_id"] == "obs-get"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/observations/missing")
        assert resp.status_code == 404

    def test_list_by_run_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/observations",
            json={
                "observation_id": "obs-r1",
                "run_id": "run-A",
                "project_id": "proj-1",
                "content": "a",
            },
        )
        client.post(
            "/api/v1/observations",
            json={
                "observation_id": "obs-r2",
                "run_id": "run-B",
                "project_id": "proj-1",
                "content": "b",
            },
        )
        resp = client.get("/api/v1/observations", params={"run_id": "run-A"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_by_project_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/observations",
            json={
                "observation_id": "obs-p1",
                "run_id": "run-1",
                "project_id": "proj-X",
                "content": "x",
            },
        )
        resp = client.get("/api/v1/observations", params={"project_id": "proj-X"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
