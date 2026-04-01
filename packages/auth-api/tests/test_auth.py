"""Tests for auth API: login, refresh, me, JWT, password hashing."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.auth_api.middleware import JWTAuthMiddleware
from lintel.auth_api.routes import auth_user_store_provider, router
from lintel.auth_api.store import InMemoryAuthUserStore
from lintel.domain.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lintel.domain.auth.passwords import hash_password, verify_password
from lintel.domain.auth.types import AuthRole, AuthUser


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("my-secret")
        assert verify_password("my-secret", hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("my-secret")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token("u-1", "admin")
        payload = decode_token(token)
        assert payload.sub == "u-1"
        assert payload.role == "admin"
        assert payload.token_type == "access"

    def test_create_and_decode_refresh_token(self) -> None:
        token = create_refresh_token("u-2", "member")
        payload = decode_token(token)
        assert payload.sub == "u-2"
        assert payload.token_type == "refresh"

    def test_expired_token_raises(self) -> None:
        import time

        import jwt as pyjwt

        from lintel.domain.auth.jwt import JWT_ALGORITHM, JWT_SECRET

        payload = {
            "sub": "u-1",
            "role": "member",
            "exp": int(time.time()) - 10,
            "iat": int(time.time()) - 100,
            "token_type": "access",
        }
        token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        import pytest

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)


class TestLoginEndpoint:
    async def test_login_success(
        self,
        seeded_store: InMemoryAuthUserStore,
    ) -> None:
        auth_user_store_provider.override(seeded_store)
        app = FastAPI()
        app.add_middleware(JWTAuthMiddleware)
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
        auth_user_store_provider.override(None)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(
        self,
        seeded_store: InMemoryAuthUserStore,
    ) -> None:
        auth_user_store_provider.override(seeded_store)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "wrong"},
            )
        auth_user_store_provider.override(None)
        assert resp.status_code == 401

    async def test_login_unknown_email(
        self,
        seeded_store: InMemoryAuthUserStore,
    ) -> None:
        auth_user_store_provider.override(seeded_store)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "x"},
            )
        auth_user_store_provider.override(None)
        assert resp.status_code == 401


class TestRefreshEndpoint:
    async def test_refresh_returns_new_access_token(
        self,
        seeded_store: InMemoryAuthUserStore,
    ) -> None:
        auth_user_store_provider.override(seeded_store)
        app = FastAPI()
        app.add_middleware(JWTAuthMiddleware)
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            refresh_token = login_resp.json()["refresh_token"]
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
        auth_user_store_provider.override(None)
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_with_access_token_fails(self) -> None:
        access = create_access_token("u-1", "member")
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": access},
            )
        assert resp.status_code == 401


class TestMeEndpoint:
    async def test_me_with_valid_token(
        self,
        seeded_store: InMemoryAuthUserStore,
    ) -> None:
        auth_user_store_provider.override(seeded_store)
        app = FastAPI()
        app.add_middleware(JWTAuthMiddleware)
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as client:
            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            token = login_resp.json()["access_token"]
            resp = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        auth_user_store_provider.override(None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"

    def test_me_without_token(self, client: TestClient) -> None:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestAuthUserStore:
    async def test_get_by_email(self) -> None:
        store = InMemoryAuthUserStore()
        user = AuthUser(
            user_id="u-1",
            email="bob@example.com",
            name="Bob",
            hashed_password="hashed",
            role=AuthRole.MEMBER,
        )
        await store.add(user)
        assert await store.get_by_email("bob@example.com") == user
        assert await store.get_by_id("u-1") == user
        assert await store.get_by_email("nobody@example.com") is None
