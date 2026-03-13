"""Tests for the metrics API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestMetricsAPI:
    def test_pii_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/pii")
        assert resp.status_code == 200
        data = resp.json()
        assert "pii" in data
        assert "total_scanned" in data["pii"]

    def test_agent_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_steps" in data
        assert "activity" in data

    def test_overview_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "pii" in data
        assert "sandboxes" in data
        assert "connections" in data

    def test_quality_metrics_default(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "coverage_deltas" in data
        assert "defect_density" in data
        assert "rework_ratio" in data
        assert data["window_days"] == 30
        assert data["defect_density"]["density"] == 0.0
        assert data["rework_ratio"]["ratio"] == 0.0

    def test_quality_metrics_with_window(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_days"] == 90

    def test_quality_metrics_with_project_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality?project_id=proj-1&days=60")
        assert resp.status_code == 200
        data = resp.json()
        assert data["defect_density"]["window_days"] == 60
