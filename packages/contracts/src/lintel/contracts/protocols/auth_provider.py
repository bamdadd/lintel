"""AuthProvider protocol — service boundary for authentication backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from lintel.contracts.auth import AuthUser, TokenPair


@runtime_checkable
class AuthProvider(Protocol):
    """Abstract authentication provider.

    Implementations may use built-in JWT (BuiltinAuthProvider),
    Keycloak, Clerk, or any other identity backend.
    Domain code depends only on this Protocol.
    """

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate with email/password and return a token pair."""
        ...

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Exchange a valid refresh token for a new token pair."""
        ...

    async def verify_token(self, token: str) -> AuthUser:
        """Decode and verify an access token, returning the authenticated user."""
        ...

    async def register(
        self,
        email: str,
        display_name: str,
        role: str,
        *,
        password: str | None = None,
    ) -> AuthUser:
        """Create a new user account and return the user."""
        ...
