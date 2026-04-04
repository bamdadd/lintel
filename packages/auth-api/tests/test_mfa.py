"""Tests for MFA endpoints (TOTP and WebAuthn)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.auth_api.mfa_routes import mfa_store_provider
from lintel.auth_api.mfa_routes import router as mfa_router
from lintel.auth_api.mfa_store import InMemoryMFAStore
from lintel.domain.auth.types import MFAMethod

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_app(user_id: str) -> FastAPI:
    """Create a FastAPI app with fake auth middleware injecting a user."""
    app = FastAPI()
    app.include_router(mfa_router, prefix="/api/v1")

    from lintel.domain.auth.jwt import TokenPayload

    @app.middleware("http")
    async def _fake_auth(request: object, call_next: object) -> object:  # type: ignore[override]
        from starlette.requests import Request as StarletteRequest

        req = request  # type: ignore[assignment]
        assert isinstance(req, StarletteRequest)
        req.state.auth_user = TokenPayload(sub=user_id, role="member", exp=0, token_type="access")
        return await call_next(req)  # type: ignore[operator]

    return app


@pytest.fixture()
def user_id() -> str:
    return str(uuid4())


@pytest.fixture()
def mfa_store() -> InMemoryMFAStore:
    return InMemoryMFAStore()


@pytest.fixture()
def client(
    user_id: str,
    mfa_store: InMemoryMFAStore,
) -> Generator[TestClient]:
    mfa_store_provider.override(mfa_store)
    app = _make_app(user_id)
    with TestClient(app) as c:
        yield c
    mfa_store_provider.override(None)


class TestTOTPSetup:
    def test_setup_returns_secret_and_uri(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/mfa/totp/setup")
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert data["provisioning_uri"].startswith("otpauth://totp/")

    def test_setup_rejects_if_already_enabled(
        self,
        client: TestClient,
        mfa_store: InMemoryMFAStore,
        user_id: str,
    ) -> None:
        import asyncio

        from lintel.domain.auth.types import MFAConfig

        asyncio.get_event_loop().run_until_complete(
            mfa_store.save(
                MFAConfig(
                    user_id=user_id,
                    method=MFAMethod.TOTP,
                    enabled=True,
                    totp_secret="EXISTING",
                )
            )
        )
        resp = client.post("/api/v1/auth/mfa/totp/setup")
        assert resp.status_code == 409


class TestTOTPVerify:
    def test_verify_valid_code_enables_totp(self, client: TestClient) -> None:
        setup_resp = client.post("/api/v1/auth/mfa/totp/setup")
        secret = setup_resp.json()["secret"]

        import pyotp

        code = pyotp.TOTP(secret).now()
        resp = client.post("/api/v1/auth/mfa/totp/verify", json={"code": code})
        assert resp.status_code == 200
        assert resp.json() == {"verified": True, "enabled": True}

    def test_verify_invalid_code_rejected(self, client: TestClient) -> None:
        client.post("/api/v1/auth/mfa/totp/setup")
        resp = client.post("/api/v1/auth/mfa/totp/verify", json={"code": "000000"})
        assert resp.status_code == 400

    def test_verify_without_setup_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/mfa/totp/verify", json={"code": "123456"})
        assert resp.status_code == 404


class TestWebAuthnRegister:
    def test_register_stores_credential(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/mfa/webauthn/register",
            json={"credential_id": "cred-abc", "attestation": "data"},
        )
        assert resp.status_code == 201
        assert resp.json()["credential_id"] == "cred-abc"


class TestWebAuthnAuthenticate:
    def test_authenticate_valid_credential(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/mfa/webauthn/register",
            json={"credential_id": "cred-xyz"},
        )
        resp = client.post(
            "/api/v1/auth/mfa/webauthn/authenticate",
            json={"credential_id": "cred-xyz"},
        )
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True

    def test_authenticate_wrong_credential(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/mfa/webauthn/register",
            json={"credential_id": "cred-xyz"},
        )
        resp = client.post(
            "/api/v1/auth/mfa/webauthn/authenticate",
            json={"credential_id": "wrong"},
        )
        assert resp.status_code == 401

    def test_authenticate_not_registered(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/mfa/webauthn/authenticate",
            json={"credential_id": "cred-xyz"},
        )
        assert resp.status_code == 404
