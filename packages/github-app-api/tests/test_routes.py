"""Tests for GitHub App installation routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.github_app_api.routes import (
    http_client_provider,
    installation_store_provider,
    router,
)
from lintel.github_app_api.store import InMemoryGitHubAppInstallationStore


@pytest.fixture()
def store() -> InMemoryGitHubAppInstallationStore:
    return InMemoryGitHubAppInstallationStore()


@pytest.fixture()
def mock_http_client() -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "account": {"login": "test-org", "type": "Organization"},
        "permissions": {"contents": "read"},
        "repository_selection": "all",
    }
    response.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


@pytest.fixture()
def app(store: InMemoryGitHubAppInstallationStore, mock_http_client: MagicMock) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    installation_store_provider.override(store)
    http_client_provider.override(mock_http_client)
    yield test_app  # type: ignore[misc]
    installation_store_provider.reset()
    http_client_provider.reset()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_install_redirect(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_APP_CLIENT_ID", "Iv1.abc123")
    monkeypatch.setenv("GITHUB_APP_SLUG", "test-app")
    resp = client.get("/api/v1/integrations/github/install", follow_redirects=False)
    assert resp.status_code == 302
    assert "github.com/apps/test-app/installations/new" in resp.headers["location"]


def test_install_redirect_no_client_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_APP_CLIENT_ID", raising=False)
    resp = client.get("/api/v1/integrations/github/install")
    assert resp.status_code == 500


def test_callback_installs(
    client: TestClient,
    store: InMemoryGitHubAppInstallationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    resp = client.get(
        "/api/v1/integrations/github/callback",
        params={"installation_id": 99, "setup_action": "install"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["installation_id"] == 99
    assert data["account_login"] == "test-org"


def test_callback_uninstall(
    client: TestClient,
    store: InMemoryGitHubAppInstallationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    # First install
    client.get(
        "/api/v1/integrations/github/callback",
        params={"installation_id": 99, "setup_action": "install"},
    )
    # Then uninstall
    resp = client.get(
        "/api/v1/integrations/github/callback",
        params={"installation_id": 99, "setup_action": "uninstall"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "uninstalled"


def test_webhook_installation_created(
    client: TestClient,
    store: InMemoryGitHubAppInstallationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_APP_WEBHOOK_SECRET", raising=False)
    payload: dict[str, Any] = {
        "action": "created",
        "installation": {
            "id": 42,
            "account": {"login": "my-org", "type": "Organization"},
            "permissions": {"issues": "write"},
            "repository_selection": "selected",
        },
    }
    resp = client.post(
        "/api/v1/integrations/github/webhook",
        json=payload,
        headers={"x-github-event": "installation"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_installation_deleted(
    client: TestClient,
    store: InMemoryGitHubAppInstallationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_APP_WEBHOOK_SECRET", raising=False)
    # Create first
    client.post(
        "/api/v1/integrations/github/webhook",
        json={
            "action": "created",
            "installation": {
                "id": 42,
                "account": {"login": "my-org", "type": "Organization"},
                "permissions": {},
                "repository_selection": "all",
            },
        },
        headers={"x-github-event": "installation"},
    )
    # Delete
    resp = client.post(
        "/api/v1/integrations/github/webhook",
        json={
            "action": "deleted",
            "installation": {"id": 42, "account": {"login": "my-org"}},
        },
        headers={"x-github-event": "installation"},
    )
    assert resp.status_code == 200


def test_webhook_signature_verification(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_APP_WEBHOOK_SECRET", "testsecret")
    resp = client.post(
        "/api/v1/integrations/github/webhook",
        json={"action": "ping"},
        headers={
            "x-github-event": "ping",
            "x-hub-signature-256": "sha256=invalid",
        },
    )
    assert resp.status_code == 401
