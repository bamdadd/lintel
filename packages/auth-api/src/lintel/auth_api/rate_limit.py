"""API rate limiting middleware — sliding window per-user and per-IP."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response

_DEFAULT_EXCLUDE: tuple[str, ...] = (
    "/healthz",
    "/docs",
    "/openapi.json",
)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    user_requests_per_minute: int = 100
    ip_requests_per_minute: int = 60
    exclude_paths: tuple[str, ...] = _DEFAULT_EXCLUDE


@dataclass
class _SlidingWindow:
    """Tracks request timestamps within a sliding window."""

    timestamps: list[float] = field(default_factory=list)

    def count_and_add(self, now: float, window_seconds: float) -> int:
        """Remove expired entries, add current timestamp, return count."""
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        self.timestamps.append(now)
        return len(self.timestamps)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-user and per-IP rate limits using a sliding window.

    Must be registered after ``JWTAuthMiddleware`` so that
    ``request.state.auth_user`` is available for per-user limiting.
    """

    def __init__(
        self,
        app: object,
        config: RateLimitConfig | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.config = config or RateLimitConfig()
        self._user_windows: dict[str, _SlidingWindow] = defaultdict(_SlidingWindow)
        self._ip_windows: dict[str, _SlidingWindow] = defaultdict(_SlidingWindow)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Response],  # type: ignore[type-arg]
    ) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.config.exclude_paths):
            return await call_next(request)  # type: ignore[return-value]

        now = time.monotonic()
        window_seconds = 60.0

        auth_user = getattr(request.state, "auth_user", None)
        if auth_user is not None:
            key = auth_user.sub
            count = self._user_windows[key].count_and_add(now, window_seconds)
            limit = self.config.user_requests_per_minute
        else:
            key = request.client.host if request.client else "unknown"
            count = self._ip_windows[key].count_and_add(now, window_seconds)
            limit = self.config.ip_requests_per_minute

        if count > limit:
            retry_after = math.ceil(window_seconds)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        response: Response = await call_next(request)  # type: ignore[assignment]
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
