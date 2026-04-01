"""Auth middleware: extract and validate JWT from Authorization header."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware

from lintel.domain.auth.jwt import decode_token

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response

# Paths that do not require authentication.
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/healthz",
    "/docs",
    "/openapi.json",
    "/mcp",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Validate JWT bearer tokens and inject user info into ``request.state``."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Response],  # type: ignore[type-arg]
    ) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)  # type: ignore[return-value]

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # Allow unauthenticated requests through (opt-in protection per route)
            request.state.auth_user = None
            return await call_next(request)  # type: ignore[return-value]

        token = auth_header[7:]
        try:
            payload = decode_token(token)
            if payload.token_type != "access":
                request.state.auth_user = None
            else:
                request.state.auth_user = payload
        except pyjwt.InvalidTokenError:
            request.state.auth_user = None

        return await call_next(request)  # type: ignore[return-value]
