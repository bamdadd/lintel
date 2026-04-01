"""Authentication endpoints — login, refresh, me, register."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.auth_dependencies import get_current_user, require_admin
from lintel.contracts.auth import TokenPair  # noqa: TC001 - must be runtime for OpenAPI schema

if TYPE_CHECKING:
    from lintel.contracts.auth import AuthUser
    from lintel.infrastructure.builtin_auth_provider import BuiltinAuthProvider

router = APIRouter(prefix="/auth", tags=["auth"])


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: str
    display_name: str
    role: str = "member"
    password: str | None = None


class UserResponse(BaseModel):
    """Public user representation (no hashed_password)."""

    id: str
    email: str
    display_name: str
    role: str
    created_at: str
    updated_at: str | None = None


def _user_response(user: AuthUser) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> TokenPair:
    """Authenticate with email and password."""
    auth_provider: BuiltinAuthProvider = request.app.state.auth_provider
    try:
        return await auth_provider.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request) -> TokenPair:
    """Exchange a refresh token for a new token pair."""
    auth_provider: BuiltinAuthProvider = request.app.state.auth_provider
    try:
        return await auth_provider.refresh(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me")
async def me(
    user: AuthUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """Return the currently authenticated user (no password hash)."""
    return _user_response(user)


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    _admin: AuthUser = Depends(require_admin),  # noqa: B008
) -> dict[str, Any]:
    """Create a new user (admin/superuser only)."""
    auth_provider: BuiltinAuthProvider = request.app.state.auth_provider
    try:
        user = await auth_provider.register(
            body.email,
            body.display_name,
            body.role,
            password=body.password,
        )
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _user_response(user)
