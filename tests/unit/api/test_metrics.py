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
