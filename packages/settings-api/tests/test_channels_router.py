"""Tests for the Slack channel connection endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.settings_api.channels_router import router

if TYPE_CHECKING:
    from collections.abc import Generator


CHANNELS = "/api/v1/settings/channels"
SLACK = f"{CHANNELS}/slack"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c


class TestListChannelConnections:
    def test_lists_slack_and_telegram(self, client: TestClient) -> None:
        resp = client.get(CHANNELS)
        assert resp.status_code == 200
        data = resp.json()
        types = {c["channel_type"] for c in data}
        assert "slack" in types
        assert "telegram" in types

    def test_slack_initially_disconnected(self, client: TestClient) -> None:
        resp = client.get(CHANNELS)
        slack = next(c for c in resp.json() if c["channel_type"] == "slack")
        assert slack["connected"] is False


class TestConnectSlack:
    def test_connect_stores_credentials(self, client: TestClient) -> None:
        resp = client.post(
            SLACK,
            json={
                "bot_token": "xoxb-test-token",
                "signing_secret": "abc123",
                "app_token": "xapp-test-token",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel_type"] == "slack"
        assert data["connected"] is True

    def test_connect_makes_slack_show_connected(self, client: TestClient) -> None:
        client.post(
            SLACK,
            json={
                "bot_token": "xoxb-test-token",
                "signing_secret": "abc123",
            },
        )
        resp = client.get(CHANNELS)
        slack = next(c for c in resp.json() if c["channel_type"] == "slack")
        assert slack["connected"] is True

    def test_connect_with_minimal_fields(self, client: TestClient) -> None:
        resp = client.post(
            SLACK,
            json={"bot_token": "xoxb-test-token"},
        )
        assert resp.status_code == 201

    def test_connect_requires_bot_token(self, client: TestClient) -> None:
        resp = client.post(SLACK, json={})
        assert resp.status_code == 422


class TestSlackStatus:
    def test_status_when_not_connected(self, client: TestClient) -> None:
        resp = client.get(f"{SLACK}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert "not configured" in data["message"].lower()

    def test_status_when_connected(self, client: TestClient) -> None:
        client.post(
            SLACK,
            json={"bot_token": "xoxb-test-token", "signing_secret": "abc123"},
        )
        resp = client.get(f"{SLACK}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["channel_type"] == "slack"


class TestDisconnectSlack:
    def test_disconnect_when_connected(self, client: TestClient) -> None:
        client.post(
            SLACK,
            json={"bot_token": "xoxb-test-token"},
        )
        resp = client.delete(SLACK)
        assert resp.status_code == 204

        # Should now be disconnected
        channels = client.get(CHANNELS).json()
        slack = next(c for c in channels if c["channel_type"] == "slack")
        assert slack["connected"] is False

    def test_disconnect_when_not_connected(self, client: TestClient) -> None:
        resp = client.delete(SLACK)
        assert resp.status_code == 404
