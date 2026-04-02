"""Tests for syntheses API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestSynthesesAPI:
    def test_create_synthesis_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/syntheses",
            json={
                "synthesis_id": "syn-1",
                "hypothesis": "Parallel execution improves throughput",
                "source_observation_ids": ["obs-1", "obs-2"],
                "project_ids": ["proj-A", "proj-B"],
                "confidence_score": 0.85,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["synthesis_id"] == "syn-1"
        assert data["confidence_score"] == 0.85

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {
            "synthesis_id": "syn-dup",
            "hypothesis": "test",
        }
        client.post("/api/v1/syntheses", json=payload)
        resp = client.post("/api/v1/syntheses", json=payload)
        assert resp.status_code == 409

    def test_get_synthesis(self, client: TestClient) -> None:
        client.post(
            "/api/v1/syntheses",
            json={"synthesis_id": "syn-get", "hypothesis": "test"},
        )
        resp = client.get("/api/v1/syntheses/syn-get")
        assert resp.status_code == 200
        assert resp.json()["synthesis_id"] == "syn-get"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/syntheses/missing")
        assert resp.status_code == 404

    def test_list_by_min_confidence(self, client: TestClient) -> None:
        client.post(
            "/api/v1/syntheses",
            json={"synthesis_id": "syn-high", "hypothesis": "h", "confidence_score": 0.9},
        )
        client.post(
            "/api/v1/syntheses",
            json={"synthesis_id": "syn-low", "hypothesis": "l", "confidence_score": 0.3},
        )
        resp = client.get("/api/v1/syntheses", params={"min_confidence": 0.7})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["synthesis_id"] == "syn-high"

    def test_list_by_project(self, client: TestClient) -> None:
        client.post(
            "/api/v1/syntheses",
            json={
                "synthesis_id": "syn-p1",
                "hypothesis": "x",
                "project_ids": ["proj-A"],
            },
        )
        resp = client.get("/api/v1/syntheses", params={"project_id": "proj-A"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
