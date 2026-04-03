"""Tests for API rate limiting middleware."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.auth_api.middleware import JWTAuthMiddleware
from lintel.auth_api.rate_limit import RateLimitConfig, RateLimitMiddleware
from lintel.domain.auth.jwt import create_access_token


def _make_app(*, config: RateLimitConfig | None = None) -> FastAPI:
    app = FastAPI()
    # RateLimit outermost, JWTAuth inside — so auth_user is set before rate check.
    app.add_middleware(RateLimitMiddleware, config=config)
    app.add_middleware(JWTAuthMiddleware)

    @app.get("/api/v1/items")
    async def list_items() -> list[str]:
        return ["a", "b"]

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRateLimitMiddleware:
    def test_allows_requests_under_limit(self) -> None:
        config = RateLimitConfig(ip_requests_per_minute=5)
        app = _make_app(config=config)
        with TestClient(app) as client:
            for _ in range(5):
                resp = client.get("/api/v1/items")
                assert resp.status_code == 200

    def test_blocks_requests_over_ip_limit(self) -> None:
        config = RateLimitConfig(ip_requests_per_minute=3)
        app = _make_app(config=config)
        with TestClient(app) as client:
            for _ in range(3):
                resp = client.get("/api/v1/items")
                assert resp.status_code == 200
            resp = client.get("/api/v1/items")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
            assert resp.json()["detail"] == "Rate limit exceeded"

    def test_blocks_requests_over_user_limit(self) -> None:
        config = RateLimitConfig(user_requests_per_minute=2)
        app = _make_app(config=config)
        token = create_access_token("user-1", "member")
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            for _ in range(2):
                resp = client.get("/api/v1/items", headers=headers)
                assert resp.status_code == 200
            resp = client.get("/api/v1/items", headers=headers)
            assert resp.status_code == 429

    def test_separate_limits_per_user(self) -> None:
        config = RateLimitConfig(user_requests_per_minute=2)
        app = _make_app(config=config)
        token_a = create_access_token("user-a", "member")
        token_b = create_access_token("user-b", "member")
        with TestClient(app) as client:
            for _ in range(2):
                resp = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token_a}"})
                assert resp.status_code == 200
            # user-a is now rate limited
            resp = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token_a}"})
            assert resp.status_code == 429
            # user-b should still be fine
            resp = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token_b}"})
            assert resp.status_code == 200

    def test_excludes_healthz(self) -> None:
        config = RateLimitConfig(ip_requests_per_minute=1)
        app = _make_app(config=config)
        with TestClient(app) as client:
            # Healthz should never be rate limited
            for _ in range(5):
                resp = client.get("/healthz")
                assert resp.status_code == 200

    def test_includes_rate_limit_headers(self) -> None:
        config = RateLimitConfig(ip_requests_per_minute=10)
        app = _make_app(config=config)
        with TestClient(app) as client:
            resp = client.get("/api/v1/items")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Limit"] == "10"
            assert resp.headers["X-RateLimit-Remaining"] == "9"

    def test_retry_after_header_on_429(self) -> None:
        config = RateLimitConfig(ip_requests_per_minute=1)
        app = _make_app(config=config)
        with TestClient(app) as client:
            client.get("/api/v1/items")
            resp = client.get("/api/v1/items")
            assert resp.status_code == 429
            assert int(resp.headers["Retry-After"]) == 60

    def test_authenticated_uses_user_limit_not_ip(self) -> None:
        config = RateLimitConfig(user_requests_per_minute=5, ip_requests_per_minute=1)
        app = _make_app(config=config)
        token = create_access_token("user-1", "member")
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            # Should use user limit (5), not ip limit (1)
            for _ in range(5):
                resp = client.get("/api/v1/items", headers=headers)
                assert resp.status_code == 200

    def test_default_config(self) -> None:
        config = RateLimitConfig()
        assert config.user_requests_per_minute == 100
        assert config.ip_requests_per_minute == 60
