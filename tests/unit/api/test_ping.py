"""Unit tests for the /ping health endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestPingEndpoint:
    def test_ping_returns_200(self, client: TestClient) -> None:
        """GET /ping must respond with HTTP 200."""
        resp = client.get("/ping")
        assert resp.status_code == 200

    def test_ping_returns_pong(self, client: TestClient) -> None:
        """Response body must be {"status": "pong"}."""
        resp = client.get("/ping")
        assert resp.json() == {"status": "pong"}

    def test_ping_content_type_is_json(self, client: TestClient) -> None:
        """Response Content-Type must be application/json."""
        resp = client.get("/ping")
        assert "application/json" in resp.headers["content-type"]

    def test_ping_status_field_is_string(self, client: TestClient) -> None:
        """The 'status' field in the response must be a string."""
        resp = client.get("/ping")
        data = resp.json()
        assert isinstance(data["status"], str)

    def test_ping_status_value_is_pong(self, client: TestClient) -> None:
        """The 'status' field must equal exactly 'pong'."""
        resp = client.get("/ping")
        assert resp.json()["status"] == "pong"

    def test_ping_response_has_no_extra_fields(self, client: TestClient) -> None:
        """Response body must contain only the 'status' key."""
        resp = client.get("/ping")
        assert set(resp.json().keys()) == {"status"}

    def test_ping_is_idempotent(self, client: TestClient) -> None:
        """Multiple calls to /ping must all return the same body."""
        responses = [client.get("/ping").json() for _ in range(3)]
        assert all(r == {"status": "pong"} for r in responses)
