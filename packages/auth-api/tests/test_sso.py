"""Tests for SSO/SAML/OIDC authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.auth_api.routes import auth_user_store_provider, router, session_store_provider
from lintel.auth_api.sso_routes import (
    sso_config_store_provider,
    sso_router,
    sso_state_store_provider,
)
from lintel.auth_api.sso_store import InMemorySSOConfigStore, InMemorySSOStateStore
from lintel.auth_api.store import InMemoryAuthUserStore, InMemorySessionStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def sso_config_store() -> InMemorySSOConfigStore:
    return InMemorySSOConfigStore()


@pytest.fixture()
def sso_state_store() -> InMemorySSOStateStore:
    return InMemorySSOStateStore()


@pytest.fixture()
def client(
    sso_config_store: InMemorySSOConfigStore,
    sso_state_store: InMemorySSOStateStore,
) -> Generator[TestClient]:
    user_store = InMemoryAuthUserStore()
    session_store = InMemorySessionStore()
    auth_user_store_provider.override(user_store)
    session_store_provider.override(session_store)
    sso_config_store_provider.override(sso_config_store)
    sso_state_store_provider.override(sso_state_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(sso_router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    auth_user_store_provider.override(None)
    session_store_provider.override(None)
    sso_config_store_provider.override(None)
    sso_state_store_provider.override(None)


class TestSSOConfigure:
    def test_configure_oidc(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Okta Corp",
                "protocol": "oidc",
                "issuer_url": "https://corp.okta.com",
                "client_id": "abc",
                "client_secret": "sec",
                "redirect_uri": "http://localhost:8000/api/v1/auth/sso/callback",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Okta Corp"
        assert data["protocol"] == "oidc"
        assert data["config_id"]
        assert data["issuer_url"] == "https://corp.okta.com"

    def test_configure_saml2(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "ADFS",
                "protocol": "saml2",
                "idp_sso_url": "https://adfs.corp.com/sso",
                "idp_entity_id": "urn:adfs",
                "sp_entity_id": "urn:lintel",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["protocol"] == "saml2"
        assert data["idp_sso_url"] == "https://adfs.corp.com/sso"

    def test_configure_oidc_missing_issuer(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={"name": "Bad", "protocol": "oidc"},
        )
        assert resp.status_code == 422

    def test_configure_saml2_missing_idp_url(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={"name": "Bad", "protocol": "saml2"},
        )
        assert resp.status_code == 422


class TestSSOList:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/auth/sso/configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_configure(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Okta",
                "protocol": "oidc",
                "issuer_url": "https://okta.example.com",
                "client_id": "c",
                "client_secret": "s",
            },
        )
        resp = client.get("/api/v1/auth/sso/configs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestSSOLogin:
    def _configure_oidc(self, client: TestClient) -> str:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Test OIDC",
                "protocol": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "cid",
                "client_secret": "csec",
                "redirect_uri": "http://localhost/callback",
            },
        )
        return resp.json()["config_id"]

    def _configure_saml(self, client: TestClient) -> str:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Test SAML",
                "protocol": "saml2",
                "idp_sso_url": "https://idp.example.com/saml/sso",
                "idp_entity_id": "urn:idp",
                "sp_entity_id": "urn:sp",
            },
        )
        return resp.json()["config_id"]

    def test_login_oidc_redirect(self, client: TestClient) -> None:
        config_id = self._configure_oidc(client)
        resp = client.get(
            "/api/v1/auth/sso/login",
            params={"config_id": config_id},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorize" in data["redirect_url"]
        assert "client_id=cid" in data["redirect_url"]
        assert data["state"]

    def test_login_saml_redirect(self, client: TestClient) -> None:
        config_id = self._configure_saml(client)
        resp = client.get(
            "/api/v1/auth/sso/login",
            params={"config_id": config_id},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "RelayState=" in data["redirect_url"]

    def test_login_not_found(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/auth/sso/login",
            params={"config_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_login_disabled_provider(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Disabled",
                "protocol": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "c",
                "client_secret": "s",
                "enabled": False,
            },
        )
        config_id = resp.json()["config_id"]
        resp = client.get(
            "/api/v1/auth/sso/login",
            params={"config_id": config_id},
        )
        assert resp.status_code == 400


class TestSSOCallback:
    def test_callback_provisions_user(self, client: TestClient) -> None:
        # Configure OIDC provider
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Test",
                "protocol": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "cid",
                "client_secret": "csec",
                "redirect_uri": "http://localhost/callback",
            },
        )
        config_id = resp.json()["config_id"]

        # Initiate login to get state
        resp = client.get(
            "/api/v1/auth/sso/login",
            params={"config_id": config_id},
        )
        state = resp.json()["state"]

        # Simulate callback with claims
        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={
                "state": state,
                "email": "newuser@corp.com",
                "name": "New User",
                "external_id": "ext-123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@corp.com"
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["provisioned"] is True

    def test_callback_existing_user(self, client: TestClient) -> None:
        # Register a user first
        client.post(
            "/api/v1/auth/register",
            json={"email": "existing@corp.com", "password": "pass123", "name": "Existing"},
        )

        # Configure + login + callback
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Test",
                "protocol": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "cid",
                "client_secret": "csec",
            },
        )
        config_id = resp.json()["config_id"]
        resp = client.get("/api/v1/auth/sso/login", params={"config_id": config_id})
        state = resp.json()["state"]
        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={"state": state, "email": "existing@corp.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["provisioned"] is False

    def test_callback_invalid_state(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/auth/sso/callback",
            params={"state": "bad-state"},
        )
        assert resp.status_code == 400

    def test_callback_state_consumed_once(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/sso/configure",
            json={
                "name": "Test",
                "protocol": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "cid",
                "client_secret": "csec",
            },
        )
        config_id = resp.json()["config_id"]
        resp = client.get("/api/v1/auth/sso/login", params={"config_id": config_id})
        state = resp.json()["state"]

        # First callback succeeds
        resp = client.get("/api/v1/auth/sso/callback", params={"state": state})
        assert resp.status_code == 200

        # Second callback with same state fails
        resp = client.get("/api/v1/auth/sso/callback", params={"state": state})
        assert resp.status_code == 400


class TestSSOStores:
    """Unit tests for SSO in-memory stores."""

    async def test_config_store_crud(self) -> None:
        from lintel.domain.auth.sso import SSOProtocol, SSOProviderConfig

        store = InMemorySSOConfigStore()
        config = SSOProviderConfig(
            config_id="c1",
            name="Test",
            protocol=SSOProtocol.OIDC,
            issuer_url="https://idp.example.com",
        )
        await store.save(config)
        assert await store.get("c1") == config
        assert len(await store.list_all()) == 1
        assert await store.delete("c1") is True
        assert await store.get("c1") is None
        assert await store.delete("c1") is False

    async def test_state_store_pop(self) -> None:
        from lintel.domain.auth.sso import SSOLoginRequest

        store = InMemorySSOStateStore()
        req = SSOLoginRequest(state="abc", config_id="c1")
        await store.save(req)
        assert await store.pop("abc") == req
        assert await store.pop("abc") is None
