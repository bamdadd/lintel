"""Tests for the settings and connections API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app

BASE = "/api/v1/settings"
CONN = f"{BASE}/connections"


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _create_connection(client: TestClient, cid: str = "c1") -> dict:
    return client.post(
        CONN,
        json={
            "connection_id": cid,
            "connection_type": "slack",
            "name": "My Slack",
            "config": {"token": "xoxb-123"},
        },
    ).json()


class TestConnectionsAPI:
    def test_create_connection(self, client: TestClient) -> None:
        resp = client.post(
            CONN,
            json={
                "connection_id": "c1",
                "connection_type": "slack",
                "name": "My Slack",
                "config": {"token": "xoxb-123"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["connection_id"] == "c1"
        assert data["connection_type"] == "slack"
        assert data["name"] == "My Slack"
        assert data["config"] == {"token": "xoxb-123"}
        assert data["status"] == "untested"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "connection_id": "c1",
            "connection_type": "slack",
            "name": "My Slack",
            "config": {},
        }
        client.post(CONN, json=body)
        resp = client.post(CONN, json=body)
        assert resp.status_code == 409

    def test_list_connections_empty(self, client: TestClient) -> None:
        resp = client.get(CONN)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_connections_populated(self, client: TestClient) -> None:
        _create_connection(client, "c1")
        _create_connection(client, "c2")
        resp = client.get(CONN)
        assert len(resp.json()) == 2

    def test_get_connection(self, client: TestClient) -> None:
        _create_connection(client, "c1")
        resp = client.get(f"{CONN}/c1")
        assert resp.status_code == 200
        assert resp.json()["connection_id"] == "c1"

    def test_get_connection_not_found(self, client: TestClient) -> None:
        resp = client.get(f"{CONN}/nope")
        assert resp.status_code == 404

    def test_update_connection_name(self, client: TestClient) -> None:
        _create_connection(client, "c1")
        resp = client.patch(f"{CONN}/c1", json={"name": "Renamed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed"
        assert data["connection_type"] == "slack"
        assert data["config"] == {"token": "xoxb-123"}

    def test_delete_connection(self, client: TestClient) -> None:
        _create_connection(client, "c1")
        resp = client.delete(f"{CONN}/c1")
        assert resp.status_code == 204
        assert client.get(f"{CONN}/c1").status_code == 404

    def test_delete_connection_not_found(self, client: TestClient) -> None:
        resp = client.delete(f"{CONN}/nope")
        assert resp.status_code == 404

    def test_test_connection(self, client: TestClient) -> None:
        _create_connection(client, "c1")
        resp = client.post(f"{CONN}/c1/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["connection_id"] == "c1"


class TestGeneralSettingsAPI:
    def test_get_settings_defaults(self, client: TestClient) -> None:
        resp = client.get(BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_name"] == "default"
        assert data["default_model_provider"] == ""
        assert data["pii_detection_enabled"] is True
        assert data["sandbox_enabled"] is True
        assert data["max_concurrent_workflows"] == 10

    def test_update_settings_partial(self, client: TestClient) -> None:
        resp = client.patch(BASE, json={"workspace_name": "acme"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_name"] == "acme"
        assert data["default_model_provider"] == ""
        assert data["pii_detection_enabled"] is True
        assert data["sandbox_enabled"] is True
        assert data["max_concurrent_workflows"] == 10
