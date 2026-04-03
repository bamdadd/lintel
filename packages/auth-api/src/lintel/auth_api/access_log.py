"""API access logging middleware — structured request/response logging."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response

_logger = structlog.get_logger("lintel.access")

_DEFAULT_EXCLUDE: tuple[str, ...] = (
    "/healthz",
    "/docs",
    "/openapi.json",
)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every API request with user identity, timing, and request metadata.

    Must be registered *before* (outermost) ``JWTAuthMiddleware`` so that
    ``request.state.auth_user`` is populated when this middleware reads it.
    """

    def __init__(
        self,
        app: object,
        exclude_paths: tuple[str, ...] = _DEFAULT_EXCLUDE,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.exclude_paths = exclude_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Response],  # type: ignore[type-arg]
    ) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exclude_paths):
            return await call_next(request)  # type: ignore[return-value]

        start = time.monotonic()
        response: Response = await call_next(request)  # type: ignore[assignment]
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        auth_user = getattr(request.state, "auth_user", None)
        user_id: str | None = auth_user.sub if auth_user else None
        user_role: str | None = auth_user.role if auth_user else None

        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent", "")

        log_kw = {
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "user_role": user_role,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        if response.status_code >= 400:
            _logger.warning("api.access", **log_kw)
        else:
            _logger.info("api.access", **log_kw)

        return response
