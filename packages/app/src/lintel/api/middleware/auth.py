"""JWT authentication middleware for FastAPI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.requests import Request

# Paths that do not require authentication.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/healthz",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/auth/login",
        "/auth/refresh",
    }
)

# Prefixes that should bypass auth (e.g. static assets, MCP).
PUBLIC_PREFIXES: tuple[str, ...] = ("/docs", "/redoc", "/mcp")


def _is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _json_response(status: int, detail: str) -> Response:
    return Response(
        content=json.dumps({"detail": detail}),
        status_code=status,
        media_type="application/json",
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract ``Authorization: Bearer <token>`` and set ``request.state.user``.

    Public paths are exempt from token verification.  The auth provider is
    read from ``request.app.state.auth_provider`` so the middleware can be
    registered before the lifespan creates the provider.  When the provider
    is not yet available (e.g. during startup probes), all non-public paths
    return 401.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        # Auth provider may not be wired yet (pre-lifespan).
        auth_provider = getattr(request.app.state, "auth_provider", None)
        if auth_provider is None:
            return _json_response(401, "Authentication not configured")

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_response(401, "Missing or malformed Authorization header")

        token = auth_header[7:]
        try:
            user = await auth_provider.verify_token(token)
        except ValueError:
            return _json_response(403, "Invalid or expired token")

        request.state.user = user
        return await call_next(request)
