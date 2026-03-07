"""Tests for CorrelationMiddleware."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import os

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)


class TestCorrelationMiddleware:
    def test_generates_correlation_id(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert "X-Correlation-ID" in resp.headers
        assert len(resp.headers["X-Correlation-ID"]) > 0

    def test_propagates_correlation_id(self, client: TestClient) -> None:
        custom_id = "test-correlation-123"
        resp = client.get("/healthz", headers={"X-Correlation-ID": custom_id})
        assert resp.headers["X-Correlation-ID"] == custom_id

    def test_different_requests_get_different_ids(self, client: TestClient) -> None:
        r1 = client.get("/healthz")
        r2 = client.get("/healthz")
        assert r1.headers["X-Correlation-ID"] != r2.headers["X-Correlation-ID"]
