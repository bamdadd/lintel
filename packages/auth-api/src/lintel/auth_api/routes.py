"""Auth endpoints: login, refresh, logout, sessions, me."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.domain.auth.jwt import (
    REFRESH_TOKEN_EXPIRES,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lintel.domain.auth.passwords import hash_password, verify_password
from lintel.domain.auth.types import AuthRole, AuthSession, AuthUser

if TYPE_CHECKING:
    from lintel.auth_api.store import InMemoryAuthUserStore, InMemorySessionStore
    from lintel.domain.auth.jwt import TokenPayload

router = APIRouter()

auth_user_store_provider: StoreProvider[InMemoryAuthUserStore] = StoreProvider()
session_store_provider: StoreProvider[InMemorySessionStore] = StoreProvider()


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    session_id: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    expires_at: str
    user_agent: str = ""
    ip_address: str = ""
    revoked: bool = False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _extract_client_info(request: Request) -> tuple[str, str]:
    """Extract user-agent and IP from the request."""
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    return ua, ip


@router.post("/auth/register", status_code=201)
async def register(
    body: RegisterRequest,
    store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
) -> dict[str, str]:
    """Register a new user with email and password."""
    existing = await store.get_by_email(body.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = AuthUser(
        user_id=str(uuid4()),
        email=body.email,
        name=body.name or body.email.split("@")[0],
        hashed_password=hash_password(body.password),
        role=AuthRole.MEMBER,
    )
    await store.add(user)
    return {"user_id": user.user_id, "email": user.email}


@router.post("/auth/login")
async def login(
    request: Request,
    body: LoginRequest,
    store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> TokenResponse:
    user = await store.get_by_email(body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    session_id = str(uuid4())
    now = _now_iso()
    expires = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() + REFRESH_TOKEN_EXPIRES,
        tz=UTC,
    ).isoformat()

    refresh_token, jti = create_refresh_token(
        user.user_id,
        user.role,
        session_id=session_id,
    )
    access_token = create_access_token(
        user.user_id,
        user.role,
        session_id=session_id,
    )

    ua, ip = _extract_client_info(request)
    session = AuthSession(
        session_id=session_id,
        user_id=user.user_id,
        refresh_token_jti=jti,
        created_at=now,
        expires_at=expires,
        user_agent=ua,
        ip_address=ip,
    )
    await sessions.create(session)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session_id,
    )


@router.post("/auth/refresh")
async def refresh(
    body: RefreshRequest,
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> AccessTokenResponse:
    import jwt as pyjwt

    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.token_type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Validate refresh token against session store
    if payload.jti:
        session = await sessions.get_by_jti(payload.jti)
        if session is not None and session.revoked:
            raise HTTPException(status_code=401, detail="Session revoked")

    return AccessTokenResponse(
        access_token=create_access_token(
            payload.sub,
            payload.role,
            session_id=payload.sid,
        ),
    )


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> None:
    """Revoke the current session."""
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if auth_user.sid:
        await sessions.revoke(auth_user.sid, _now_iso())


@router.post("/auth/logout-all", status_code=204)
async def logout_all(
    request: Request,
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> None:
    """Revoke all sessions for the current user."""
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await sessions.revoke_all_for_user(auth_user.sub, _now_iso())


@router.get("/auth/sessions")
async def list_sessions(
    request: Request,
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> list[SessionInfo]:
    """List active sessions for the current user."""
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_sessions = await sessions.list_for_user(auth_user.sub)
    return [
        SessionInfo(
            session_id=s.session_id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            revoked=s.revoked,
        )
        for s in user_sessions
    ]


@router.delete("/auth/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    request: Request,
    sessions: InMemorySessionStore = Depends(session_store_provider),  # noqa: B008
) -> None:
    """Revoke a specific session."""
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await sessions.get(session_id)
    if session is None or session.user_id != auth_user.sub:
        raise HTTPException(status_code=404, detail="Session not found")
    await sessions.revoke(session_id, _now_iso())


@router.get("/auth/me")
async def me(
    request: Request,
    store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await store.get_by_id(auth_user.sub)
    if user is not None:
        return {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        }
    return {"user_id": auth_user.sub, "role": auth_user.role}
