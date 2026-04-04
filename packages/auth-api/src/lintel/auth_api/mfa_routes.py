"""MFA endpoints: TOTP setup/verify, WebAuthn register/authenticate."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.domain.auth.totp import generate_totp_secret, get_provisioning_uri, verify_totp_code
from lintel.domain.auth.types import MFAConfig, MFAMethod

if TYPE_CHECKING:
    from lintel.auth_api.mfa_store import InMemoryMFAStore
    from lintel.domain.auth.jwt import TokenPayload

router = APIRouter()

mfa_store_provider: StoreProvider[InMemoryMFAStore] = StoreProvider()


def _get_auth_user(request: Request) -> TokenPayload:
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth_user


class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TOTPVerifyRequest(BaseModel):
    code: str


class WebAuthnRegisterRequest(BaseModel):
    credential_id: str
    attestation: str = ""


class WebAuthnAuthenticateRequest(BaseModel):
    credential_id: str
    assertion: str = ""


@router.post("/auth/mfa/totp/setup")
async def totp_setup(request: Request) -> TOTPSetupResponse:
    """Generate a TOTP secret for the authenticated user."""
    auth_user = _get_auth_user(request)
    store = mfa_store_provider.get()

    existing = await store.get(auth_user.sub, MFAMethod.TOTP)
    if existing is not None and existing.enabled:
        raise HTTPException(status_code=409, detail="TOTP already enabled")

    secret = generate_totp_secret()
    config = MFAConfig(
        user_id=auth_user.sub,
        method=MFAMethod.TOTP,
        enabled=False,
        totp_secret=secret,
        created_at=datetime.now(UTC).isoformat(),
    )
    await store.save(config)

    uri = get_provisioning_uri(secret, auth_user.sub)
    return TOTPSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/auth/mfa/totp/verify")
async def totp_verify(request: Request, body: TOTPVerifyRequest) -> dict[str, bool]:
    """Verify a TOTP code and enable TOTP if valid."""
    auth_user = _get_auth_user(request)
    store = mfa_store_provider.get()

    config = await store.get(auth_user.sub, MFAMethod.TOTP)
    if config is None:
        raise HTTPException(status_code=404, detail="TOTP not set up")

    if not verify_totp_code(config.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    await store.enable(auth_user.sub, MFAMethod.TOTP)
    return {"verified": True, "enabled": True}


@router.post("/auth/mfa/webauthn/register", status_code=201)
async def webauthn_register(
    request: Request,
    body: WebAuthnRegisterRequest,
) -> dict[str, str]:
    """Register a WebAuthn credential (stub — stores credential_id only)."""
    auth_user = _get_auth_user(request)
    store = mfa_store_provider.get()

    config = MFAConfig(
        user_id=auth_user.sub,
        method=MFAMethod.WEBAUTHN,
        enabled=True,
        webauthn_credential_id=body.credential_id,
        created_at=datetime.now(UTC).isoformat(),
    )
    await store.save(config)
    return {"credential_id": body.credential_id, "status": "registered"}


@router.post("/auth/mfa/webauthn/authenticate")
async def webauthn_authenticate(
    request: Request,
    body: WebAuthnAuthenticateRequest,
) -> dict[str, bool]:
    """Authenticate with a WebAuthn credential (stub — checks credential_id exists)."""
    auth_user = _get_auth_user(request)
    store = mfa_store_provider.get()

    config = await store.get(auth_user.sub, MFAMethod.WEBAUTHN)
    if config is None or not config.enabled:
        raise HTTPException(status_code=404, detail="WebAuthn not registered")

    if config.webauthn_credential_id != body.credential_id:
        raise HTTPException(status_code=401, detail="Invalid credential")

    return {"authenticated": True}
