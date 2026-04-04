"""Tests for Slack OAuth install flow endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.settings_api.channels_router import router

if TYPE_CHECKING:
    from collections.abc import Generator

INSTALL = "/api/v1/settings/channels/slack/install"
CALLBACK = "/api/v1/settings/channels/slack/oauth/callback"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def oauth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    """Client with Slack OAuth env vars configured."""
    monkeypatch.setenv("SLACK_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "test-client-secret")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestSlackInstall:
    def test_redirects_to_slack(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(INSTALL, follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.hostname == "slack.com"
        assert "/oauth/v2/authorize" in parsed.path
        qs = parse_qs(parsed.query)
        assert qs["client_id"] == ["test-client-id"]
        assert "state" in qs

    def test_includes_scopes(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(INSTALL, follow_redirects=False)
        location = resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        assert "chat:write" in qs["scope"][0]

    def test_fails_without_client_id(self, client: TestClient) -> None:
        resp = client.get(INSTALL, follow_redirects=False)
        assert resp.status_code == 400
        assert "SLACK_CLIENT_ID" in resp.json()["detail"]

    def test_stores_state_for_csrf(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(INSTALL, follow_redirects=False)
        location = resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]
        # State should be stored in app state
        assert state in oauth_client.app.state._slack_oauth_states


class TestSlackOAuthCallback:
    def test_error_param_returns_400(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(CALLBACK, params={"error": "access_denied"})
        assert resp.status_code == 400
        assert "access_denied" in resp.json()["detail"]

    def test_missing_code_returns_400(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(CALLBACK)
        assert resp.status_code == 400
        assert "Missing code" in resp.json()["detail"]

    def test_invalid_state_returns_400(self, oauth_client: TestClient) -> None:
        resp = oauth_client.get(CALLBACK, params={"code": "test-code", "state": "bad-state"})
        assert resp.status_code == 400
        assert "state" in resp.json()["detail"].lower()

    def test_successful_token_exchange(self, oauth_client: TestClient) -> None:
        # First get an install redirect to generate a valid state
        install_resp = oauth_client.get(INSTALL, follow_redirects=False)
        location = install_resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-new-bot-token",
            "team": {"id": "T12345", "name": "Test Team"},
            "bot_user_id": "U12345",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            resp = oauth_client.get(CALLBACK, params={"code": "test-code", "state": state})

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["team_id"] == "T12345"
        assert data["team_name"] == "Test Team"
        assert data["bot_user_id"] == "U12345"

    def test_slack_api_error_returns_400(self, oauth_client: TestClient) -> None:
        install_resp = oauth_client.get(INSTALL, follow_redirects=False)
        location = install_resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_code",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            resp = oauth_client.get(CALLBACK, params={"code": "bad-code", "state": state})

        assert resp.status_code == 400
        assert "invalid_code" in resp.json()["detail"]

    def test_state_is_consumed_after_use(self, oauth_client: TestClient) -> None:
        install_resp = oauth_client.get(INSTALL, follow_redirects=False)
        location = install_resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-token",
            "team": {"id": "T1", "name": "Team"},
            "bot_user_id": "U1",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            oauth_client.get(CALLBACK, params={"code": "c", "state": state})

        # Same state should now be rejected
        resp = oauth_client.get(CALLBACK, params={"code": "c", "state": state})
        assert resp.status_code == 400
