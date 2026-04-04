"""Workspace isolation middleware: extract workspace_id from JWT or header."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response

# Header name clients can use to specify workspace context.
WORKSPACE_HEADER = "X-Workspace-Id"

# Paths that don't require workspace scoping.
_UNSCOPED_PREFIXES: tuple[str, ...] = (
    "/healthz",
    "/docs",
    "/openapi.json",
    "/api/v1/auth/",
    "/api/v1/workspaces",
)


class WorkspaceIsolationMiddleware(BaseHTTPMiddleware):
    """Extract workspace_id and inject it into ``request.state.workspace_id``.

    Resolution order:
    1. ``X-Workspace-Id`` header (explicit)
    2. ``workspace_id`` claim from JWT (via ``request.state.auth_user``)
    3. ``None`` for unscoped paths
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Response],  # type: ignore[type-arg]
    ) -> Response:
        path = request.url.path

        # Unscoped paths get no workspace context.
        if any(path.startswith(prefix) for prefix in _UNSCOPED_PREFIXES):
            request.state.workspace_id = None
            return await call_next(request)  # type: ignore[return-value]

        # 1. Explicit header
        workspace_id = request.headers.get(WORKSPACE_HEADER)

        # 2. JWT claim
        if workspace_id is None:
            auth_user = getattr(request.state, "auth_user", None)
            if auth_user is not None:
                workspace_id = getattr(auth_user, "workspace_id", None)

        request.state.workspace_id = workspace_id
        return await call_next(request)  # type: ignore[return-value]
