"""Tests for the admin API endpoints."""

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


class TestAdminAPI:
    def test_reset_projections(self, client: TestClient) -> None:
        resp = client.post("/api/v1/admin/reset-projections")
        assert resp.status_code == 200
        assert resp.json()["status"] == "projections_reset"

    def test_cache_stats_returns_dict(self, client: TestClient) -> None:
        resp = client.get("/api/v1/admin/cache-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "hits" in data
        assert "misses" in data
        assert "size" in data

    def test_cache_clear(self, client: TestClient) -> None:
        resp = client.post("/api/v1/admin/cache-clear")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cache_cleared"
        # Stats should be zeroed
        stats = client.get("/api/v1/admin/cache-stats").json()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
