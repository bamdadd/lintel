"""Tests for the event API endpoints."""

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


class TestEventAPI:
    def test_list_events(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_events_by_stream(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/stream/some-stream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stream_id"] == "some-stream"
        assert isinstance(data["events"], list)

    def test_get_events_by_correlation(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/correlation/some-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["correlation_id"] == "some-id"
        assert isinstance(data["events"], list)
