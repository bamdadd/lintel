"""Built-in JWT authentication provider using PyJWT and stdlib password hashing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import TYPE_CHECKING, Any

import jwt

from lintel.contracts.auth import AuthUser, TokenPair, UserRole

if TYPE_CHECKING:
    from lintel.config import AuthSettings
    from lintel.users.auth_user_store import AuthUserStore


class BuiltinAuthProvider:
    """AuthProvider implementation backed by Postgres users and HS256 JWTs.

    Password hashing uses SHA-256 with a per-user random salt stored as
    ``<hex_salt>$<hex_hash>`` — no external library required.
    """

    def __init__(self, user_store: AuthUserStore, settings: AuthSettings) -> None:
        self._store = user_store
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_minutes = settings.jwt_access_token_expire_minutes
        self._refresh_days = settings.jwt_refresh_token_expire_days

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Return ``salt$hash`` string for storage."""
        salt = secrets.token_hex(16)
        h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}${h}"

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        """Check a plain password against a ``salt$hash`` stored value."""
        salt, expected = stored.split("$", 1)
        h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(h, expected)

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _create_token_pair(self, user: AuthUser) -> TokenPair:
        now = datetime.now(UTC)
        access_payload: dict[str, Any] = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self._access_minutes),
        }
        refresh_payload: dict[str, Any] = {
            "sub": str(user.id),
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self._refresh_days),
        }
        access_token = jwt.encode(access_payload, self._secret, algorithm=self._algorithm)
        refresh_token = jwt.encode(refresh_payload, self._secret, algorithm=self._algorithm)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    # ------------------------------------------------------------------
    # AuthProvider interface
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate with email/password and return a token pair."""
        user = await self._store.get_by_email(email)
        if user is None:
            msg = "Invalid email or password"
            raise ValueError(msg)
        if not self.verify_password(password, user.hashed_password):
            msg = "Invalid email or password"
            raise ValueError(msg)
        return self._create_token_pair(user)

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Exchange a valid refresh token for a new token pair."""
        try:
            payload = jwt.decode(refresh_token, self._secret, algorithms=[self._algorithm])
        except jwt.InvalidTokenError as exc:
            msg = "Invalid or expired refresh token"
            raise ValueError(msg) from exc

        if payload.get("type") != "refresh":
            msg = "Token is not a refresh token"
            raise ValueError(msg)

        from uuid import UUID

        user = await self._store.get(UUID(payload["sub"]))
        if user is None:
            msg = "User no longer exists"
            raise ValueError(msg)
        return self._create_token_pair(user)

    async def verify_token(self, token: str) -> AuthUser:
        """Decode and verify an access token, returning the authenticated user."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.InvalidTokenError as exc:
            msg = "Invalid or expired access token"
            raise ValueError(msg) from exc

        if payload.get("type") != "access":
            msg = "Token is not an access token"
            raise ValueError(msg)

        from uuid import UUID

        user = await self._store.get(UUID(payload["sub"]))
        if user is None:
            msg = "User no longer exists"
            raise ValueError(msg)
        return user

    async def register(
        self,
        email: str,
        display_name: str,
        role: str,
        *,
        password: str | None = None,
    ) -> AuthUser:
        """Create a new user account and return the user."""
        if password is None:
            password = secrets.token_urlsafe(24)
        hashed = self.hash_password(password)
        # Validate role
        UserRole(role)
        return await self._store.create(
            email=email,
            display_name=display_name,
            role=role,
            hashed_password=hashed,
        )
