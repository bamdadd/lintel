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
from lintel.domain.auth.passwords import verify_password

if TYPE_CHECKING:
    from lintel.auth_api.store import InMemoryAuthUserStore
    from lintel.domain.auth.jwt import TokenPayload

router = APIRouter()

auth_user_store_provider: StoreProvider[InMemoryAuthUserStore] = StoreProvider()


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
async def me(request: Request) -> dict[str, Any]:
    auth_user: TokenPayload | None = getattr(request.state, "auth_user", None)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": auth_user.sub, "role": auth_user.role}
