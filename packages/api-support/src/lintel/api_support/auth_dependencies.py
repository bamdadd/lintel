"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from lintel.contracts.auth import AuthUser


def get_current_user(request: Request) -> AuthUser:
    """Extract the authenticated user from ``request.state``.

    The :class:`AuthMiddleware` sets ``request.state.user`` for every
    authenticated request.  This dependency makes it easy to declare
    the requirement in route signatures::

        @router.get("/me")
        async def me(user: AuthUser = Depends(get_current_user)):
            ...
    """
    user: AuthUser | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> AuthUser:
    """Like :func:`get_current_user` but also asserts admin or superuser role."""
    user = get_current_user(request)
    if user.role not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
