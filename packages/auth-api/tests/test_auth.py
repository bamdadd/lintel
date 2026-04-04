"""Tests for auth API: login, refresh, logout, sessions, me, JWT, password hashing."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.auth_api.middleware import JWTAuthMiddleware
from lintel.auth_api.routes import auth_user_store_provider, router, session_store_provider
from lintel.auth_api.store import InMemoryAuthUserStore, InMemorySessionStore
from lintel.domain.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lintel.domain.auth.passwords import hash_password, verify_password
from lintel.domain.auth.types import AuthRole, AuthUser


def _make_app(
    user_store: InMemoryAuthUserStore,
    sess_store: InMemorySessionStore | None = None,
) -> FastAPI:
    """Helper to build a test app with stores wired."""
    auth_user_store_provider.override(user_store)
    session_store_provider.override(sess_store or InMemorySessionStore())
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)
    app.include_router(router, prefix="/api/v1")
    return app


def _cleanup() -> None:
    auth_user_store_provider.override(None)
    session_store_provider.override(None)


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
        token, jti = create_refresh_token("u-2", "member")
        payload = decode_token(token)
        assert payload.sub == "u-2"
        assert payload.token_type == "refresh"
        assert payload.jti == jti
        assert jti != ""

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

    def test_session_id_in_tokens(self) -> None:
        access = create_access_token("u-1", "admin", session_id="sess-1")
        payload = decode_token(access)
        assert payload.sid == "sess-1"

        refresh, _jti = create_refresh_token("u-1", "admin", session_id="sess-1")
        payload = decode_token(refresh)
        assert payload.sid == "sess-1"


class TestRegisterEndpoint:
    def test_register_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "secret123", "name": "New User"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "user_id" in data

    def test_register_duplicate_email(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "secret123"},
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "other"},
        )
        assert resp.status_code == 409

    def test_register_then_login(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/register",
            json={"email": "logintest@example.com", "password": "mypass"},
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "logintest@example.com", "password": "mypass"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


class TestLoginEndpoint:
    async def test_login_success(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
        _cleanup()
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["session_id"] != ""

    async def test_login_creates_session(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
        _cleanup()
        session_id = resp.json()["session_id"]
        session = await session_store.get(session_id)
        assert session is not None
        assert not session.revoked

    async def test_login_wrong_password(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "wrong"},
            )
        _cleanup()
        assert resp.status_code == 401

    async def test_login_unknown_email(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "x"},
            )
        _cleanup()
        assert resp.status_code == 401


class TestRefreshEndpoint:
    async def test_refresh_returns_new_access_token(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
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
        _cleanup()
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_rejected_after_session_revoked(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            data = login_resp.json()
            token = data["access_token"]
            refresh_token = data["refresh_token"]

            # Logout to revoke the session
            client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Refresh should now fail
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
        _cleanup()
        assert resp.status_code == 401

    def test_refresh_with_access_token_fails(self, client: TestClient) -> None:
        access = create_access_token("u-1", "member")
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access},
        )
        assert resp.status_code == 401


class TestLogoutEndpoint:
    async def test_logout_revokes_session(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            data = login_resp.json()
            token = data["access_token"]
            session_id = data["session_id"]

            resp = client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
        _cleanup()
        assert resp.status_code == 204
        session = await session_store.get(session_id)
        assert session is not None
        assert session.revoked

    def test_logout_without_auth(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    async def test_logout_all(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            # Login twice to create two sessions
            login1 = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            login2 = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            token = login2.json()["access_token"]

            resp = client.post(
                "/api/v1/auth/logout-all",
                headers={"Authorization": f"Bearer {token}"},
            )
        _cleanup()
        assert resp.status_code == 204
        s1 = await session_store.get(login1.json()["session_id"])
        s2 = await session_store.get(login2.json()["session_id"])
        assert s1 is not None and s1.revoked
        assert s2 is not None and s2.revoked


class TestSessionsEndpoint:
    async def test_list_sessions(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            token = login_resp.json()["access_token"]
            resp = client.get(
                "/api/v1/auth/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
        _cleanup()
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == login_resp.json()["session_id"]

    async def test_revoke_specific_session(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
        with TestClient(app) as client:
            login1 = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            login2 = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": "correct-password"},
            )
            token = login2.json()["access_token"]
            session1_id = login1.json()["session_id"]

            resp = client.delete(
                f"/api/v1/auth/sessions/{session1_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        _cleanup()
        assert resp.status_code == 204
        s1 = await session_store.get(session1_id)
        assert s1 is not None and s1.revoked
        # Second session should still be active
        s2 = await session_store.get(login2.json()["session_id"])
        assert s2 is not None and not s2.revoked

    def test_revoke_nonexistent_session(self, client: TestClient) -> None:
        # Register + login to get a token
        client.post(
            "/api/v1/auth/register",
            json={"email": "bob@example.com", "password": "pass"},
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "bob@example.com", "password": "pass"},
        )
        token = login_resp.json()["access_token"]
        resp = client.delete(
            "/api/v1/auth/sessions/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestMeEndpoint:
    async def test_me_with_valid_token(
        self,
        seeded_store: InMemoryAuthUserStore,
        session_store: InMemorySessionStore,
    ) -> None:
        app = _make_app(seeded_store, session_store)
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
        _cleanup()
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"

    def test_me_without_token(self, client: TestClient) -> None:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestSessionStore:
    async def test_create_and_get(self) -> None:
        from lintel.domain.auth.types import AuthSession

        store = InMemorySessionStore()
        session = AuthSession(
            session_id="s-1",
            user_id="u-1",
            refresh_token_jti="jti-1",
            created_at="2024-01-01T00:00:00Z",
            expires_at="2024-01-08T00:00:00Z",
        )
        await store.create(session)
        assert await store.get("s-1") == session
        assert await store.get("nonexistent") is None

    async def test_get_by_jti(self) -> None:
        from lintel.domain.auth.types import AuthSession

        store = InMemorySessionStore()
        session = AuthSession(
            session_id="s-1",
            user_id="u-1",
            refresh_token_jti="jti-1",
            created_at="2024-01-01T00:00:00Z",
            expires_at="2024-01-08T00:00:00Z",
        )
        await store.create(session)
        result = await store.get_by_jti("jti-1")
        assert result is not None
        assert result.session_id == "s-1"
        assert await store.get_by_jti("unknown") is None

    async def test_list_for_user(self) -> None:
        from lintel.domain.auth.types import AuthSession

        store = InMemorySessionStore()
        for i in range(3):
            await store.create(
                AuthSession(
                    session_id=f"s-{i}",
                    user_id="u-1",
                    refresh_token_jti=f"jti-{i}",
                    created_at="2024-01-01T00:00:00Z",
                    expires_at="2024-01-08T00:00:00Z",
                )
            )
        sessions = await store.list_for_user("u-1")
        assert len(sessions) == 3
        assert await store.list_for_user("u-other") == []

    async def test_revoke(self) -> None:
        from lintel.domain.auth.types import AuthSession

        store = InMemorySessionStore()
        await store.create(
            AuthSession(
                session_id="s-1",
                user_id="u-1",
                refresh_token_jti="jti-1",
                created_at="2024-01-01T00:00:00Z",
                expires_at="2024-01-08T00:00:00Z",
            )
        )
        assert await store.revoke("s-1", "2024-01-02T00:00:00Z")
        session = await store.get("s-1")
        assert session is not None
        assert session.revoked
        assert session.revoked_at == "2024-01-02T00:00:00Z"
        assert not await store.revoke("nonexistent", "2024-01-02T00:00:00Z")

    async def test_revoke_all_for_user(self) -> None:
        from lintel.domain.auth.types import AuthSession

        store = InMemorySessionStore()
        for i in range(2):
            await store.create(
                AuthSession(
                    session_id=f"s-{i}",
                    user_id="u-1",
                    refresh_token_jti=f"jti-{i}",
                    created_at="2024-01-01T00:00:00Z",
                    expires_at="2024-01-08T00:00:00Z",
                )
            )
        count = await store.revoke_all_for_user("u-1", "2024-01-02T00:00:00Z")
        assert count == 2
        for i in range(2):
            s = await store.get(f"s-{i}")
            assert s is not None and s.revoked


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
