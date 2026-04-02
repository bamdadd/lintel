"""Auth endpoints: login, refresh, me."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.domain.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lintel.domain.auth.passwords import hash_password, verify_password
from lintel.domain.auth.types import AuthRole, AuthUser

if TYPE_CHECKING:
    from lintel.auth_api.store import InMemoryAuthUserStore
    from lintel.domain.auth.jwt import TokenPayload

router = APIRouter()

auth_user_store_provider: StoreProvider[InMemoryAuthUserStore] = StoreProvider()


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


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/register", status_code=201)
async def register(
    body: RegisterRequest,
    store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
) -> dict[str, str]:
    """Register a new user with email and password."""
    from uuid import uuid4

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
    body: LoginRequest,
    store: InMemoryAuthUserStore = Depends(auth_user_store_provider),  # noqa: B008
) -> TokenResponse:
    user = await store.get_by_email(body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.user_id, user.role),
        refresh_token=create_refresh_token(user.user_id, user.role),
    )


@router.post("/auth/refresh")
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    import jwt as pyjwt

    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.token_type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return AccessTokenResponse(
        access_token=create_access_token(payload.sub, payload.role),
    )


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
        return {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role}
    return {"user_id": auth_user.sub, "role": auth_user.role}
