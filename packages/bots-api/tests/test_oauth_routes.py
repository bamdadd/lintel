"""Tests for per-bot Slack OAuth install flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.bots_api.oauth_routes import (
    _decode_state,
    _encode_state,
    oauth_slack_bot_store_provider,
    router,
)
from lintel.multi_slack_bot_api.store import InMemorySlackBotStore

if TYPE_CHECKING:
    from collections.abc import Generator

INSTALL = "/api/v1/bots/slack/install"
CALLBACK = "/api/v1/bots/slack/oauth/callback"


@pytest.fixture()
def slack_bot_store() -> InMemorySlackBotStore:
    return InMemorySlackBotStore()


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch,
    slack_bot_store: InMemorySlackBotStore,
) -> Generator[TestClient]:
    monkeypatch.setenv("SLACK_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "test-client-secret")
    oauth_slack_bot_store_provider.override(slack_bot_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    oauth_slack_bot_store_provider.override(None)


@pytest.fixture()
def unconfigured_client(
    slack_bot_store: InMemorySlackBotStore,
) -> Generator[TestClient]:
    oauth_slack_bot_store_provider.override(slack_bot_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    oauth_slack_bot_store_provider.override(None)


def _mock_token_exchange(  # noqa: ANN202
    *,
    ok: bool = True,
    access_token: str = "xoxb-new-bot-token",
    team_id: str = "T12345",
    team_name: str = "Test Team",
    bot_user_id: str = "U12345",
    error: str = "",
):
    """Return a context manager that mocks the httpx token exchange."""
    response_data: dict = {"ok": ok}
    if ok:
        response_data.update(
            {
                "access_token": access_token,
                "team": {"id": team_id, "name": team_name},
                "bot_user_id": bot_user_id,
            }
        )
    else:
        response_data["error"] = error

    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    return patch("httpx.AsyncClient", return_value=mock_client)


def _do_install(client: TestClient, project_id: str = "proj-1") -> tuple[str, str]:
    """Perform install redirect and return (state, csrf_token) from the redirect URL."""
    resp = client.get(INSTALL, params={"project_id": project_id}, follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    qs = parse_qs(urlparse(location).query)
    state = qs["state"][0]
    decoded = _decode_state(state)
    return state, decoded["csrf"]


class TestStateEncoding:
    def test_roundtrip(self) -> None:
        encoded = _encode_state("csrf-123", "proj-abc")
        decoded = _decode_state(encoded)
        assert decoded["csrf"] == "csrf-123"
        assert decoded["project_id"] == "proj-abc"

    def test_invalid_state_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid state"):
            _decode_state("not-valid-base64!!!")


class TestBotSlackInstall:
    def test_redirects_to_slack(self, client: TestClient) -> None:
        resp = client.get(INSTALL, params={"project_id": "proj-1"}, follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.hostname == "slack.com"
        assert "/oauth/v2/authorize" in parsed.path

    def test_state_contains_project_id(self, client: TestClient) -> None:
        resp = client.get(INSTALL, params={"project_id": "proj-42"}, follow_redirects=False)
        qs = parse_qs(urlparse(resp.headers["location"]).query)
        state = qs["state"][0]
        decoded = _decode_state(state)
        assert decoded["project_id"] == "proj-42"
        assert decoded["csrf"]

    def test_includes_client_id_and_scopes(self, client: TestClient) -> None:
        resp = client.get(INSTALL, params={"project_id": "proj-1"}, follow_redirects=False)
        qs = parse_qs(urlparse(resp.headers["location"]).query)
        assert qs["client_id"] == ["test-client-id"]
        assert "chat:write" in qs["scope"][0]

    def test_missing_project_id_returns_400(self, client: TestClient) -> None:
        resp = client.get(INSTALL, follow_redirects=False)
        assert resp.status_code == 400
        assert "project_id" in resp.json()["detail"]

    def test_missing_client_id_returns_400(self, unconfigured_client: TestClient) -> None:
        resp = unconfigured_client.get(
            INSTALL, params={"project_id": "proj-1"}, follow_redirects=False
        )
        assert resp.status_code == 400
        assert "SLACK_CLIENT_ID" in resp.json()["detail"]

    def test_csrf_state_stored(self, client: TestClient) -> None:
        _state, csrf = _do_install(client)
        assert csrf in client.app.state._bot_oauth_states


class TestBotSlackOAuthCallback:
    def test_error_param_returns_400(self, client: TestClient) -> None:
        resp = client.get(CALLBACK, params={"error": "access_denied"})
        assert resp.status_code == 400
        assert "access_denied" in resp.json()["detail"]

    def test_missing_code_returns_400(self, client: TestClient) -> None:
        resp = client.get(CALLBACK)
        assert resp.status_code == 400
        assert "Missing code" in resp.json()["detail"]

    def test_missing_state_returns_400(self, client: TestClient) -> None:
        resp = client.get(CALLBACK, params={"code": "test-code"})
        assert resp.status_code == 400
        assert "Missing state" in resp.json()["detail"]

    def test_invalid_state_returns_400(self, client: TestClient) -> None:
        resp = client.get(CALLBACK, params={"code": "test-code", "state": "bad"})
        assert resp.status_code == 400
        assert "Invalid state" in resp.json()["detail"]

    def test_expired_csrf_returns_400(self, client: TestClient) -> None:
        # Forge a valid-looking state but with unknown CSRF
        state = _encode_state("unknown-csrf", "proj-1")
        resp = client.get(CALLBACK, params={"code": "test-code", "state": state})
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower() or "Invalid" in resp.json()["detail"]

    def test_successful_install_creates_slack_bot(
        self, client: TestClient, slack_bot_store: InMemorySlackBotStore
    ) -> None:
        state, _csrf = _do_install(client, project_id="proj-1")

        with _mock_token_exchange():
            resp = client.get(CALLBACK, params={"code": "test-code", "state": state})

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["project_id"] == "proj-1"
        assert data["team_id"] == "T12345"
        assert data["team_name"] == "Test Team"
        assert data["bot_user_id"] == "U12345"
        assert data["bot_id"] == "slack-bot-T12345-proj-1"

    def test_slack_bot_stored_with_project_binding(
        self, client: TestClient, slack_bot_store: InMemorySlackBotStore
    ) -> None:
        state, _csrf = _do_install(client, project_id="proj-99")

        with _mock_token_exchange(team_id="T999", team_name="Team 99"):
            client.get(CALLBACK, params={"code": "test-code", "state": state})

        import asyncio

        bot = asyncio.get_event_loop().run_until_complete(
            slack_bot_store.get("slack-bot-T999-proj-99")
        )
        assert bot is not None
        assert bot.workspace_id == "T999"
        assert bot.project_bindings == ["proj-99"]
        assert bot.bot_token == "xoxb-new-bot-token"

    def test_state_consumed_after_use(self, client: TestClient) -> None:
        state, _csrf = _do_install(client)

        with _mock_token_exchange():
            client.get(CALLBACK, params={"code": "test-code", "state": state})

        # Replay should fail
        resp = client.get(CALLBACK, params={"code": "test-code", "state": state})
        assert resp.status_code == 400

    def test_slack_api_error_returns_400(self, client: TestClient) -> None:
        state, _csrf = _do_install(client)

        with _mock_token_exchange(ok=False, error="invalid_code"):
            resp = client.get(CALLBACK, params={"code": "bad", "state": state})

        assert resp.status_code == 400
        assert "invalid_code" in resp.json()["detail"]

    def test_duplicate_install_updates_token(
        self, client: TestClient, slack_bot_store: InMemorySlackBotStore
    ) -> None:
        # First install
        state1, _ = _do_install(client, project_id="proj-1")
        with _mock_token_exchange(access_token="xoxb-first"):
            client.get(CALLBACK, params={"code": "c1", "state": state1})

        # Second install for same project+team
        state2, _ = _do_install(client, project_id="proj-1")
        with _mock_token_exchange(access_token="xoxb-second"):
            resp = client.get(CALLBACK, params={"code": "c2", "state": state2})

        assert resp.status_code == 200

        import asyncio

        bot = asyncio.get_event_loop().run_until_complete(
            slack_bot_store.get("slack-bot-T12345-proj-1")
        )
        assert bot is not None
        assert bot.bot_token == "xoxb-second"

    def test_credential_store_called(self, client: TestClient) -> None:
        cred_store = MagicMock()
        cred_store.store = AsyncMock()
        client.app.state.credential_store = cred_store

        state, _csrf = _do_install(client, project_id="proj-1")
        with _mock_token_exchange():
            client.get(CALLBACK, params={"code": "c", "state": state})

        cred_store.store.assert_called_once()
        call_kwargs = cred_store.store.call_args.kwargs
        assert call_kwargs["credential_id"] == "bot:slack-bot-T12345-proj-1"
        assert call_kwargs["credential_type"] == "slack_bot_token"
        assert "xoxb-new-bot-token" in call_kwargs["secret"]
