"""External authentication provider integration.

Supports OIDC-based providers (Keycloak, Clerk, Auth0, Okta) with token
validation, local role mapping, and provider registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from lintel.domain.auth.types import AuthRole


class ExternalAuthProvider(StrEnum):
    """Supported external authentication providers."""

    KEYCLOAK = "keycloak"
    CLERK = "clerk"
    AUTH0 = "auth0"
    OKTA = "okta"


@dataclass(frozen=True)
class OIDCConfig:
    """OIDC connection configuration for an external provider."""

    provider: ExternalAuthProvider
    issuer_url: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...] = ("openid", "profile", "email")
    redirect_uri: str = ""


@dataclass(frozen=True)
class ExternalAuthUser:
    """User identity as returned by an external auth provider."""

    provider: ExternalAuthProvider
    external_id: str
    email: str
    name: str
    groups: tuple[str, ...] = ()
    raw_claims: dict[str, Any] = field(default_factory=dict)


# Default mapping from external group names to local AuthRole.
_DEFAULT_GROUP_ROLE_MAP: dict[str, AuthRole] = {
    "admin": AuthRole.ADMIN,
    "admins": AuthRole.ADMIN,
    "superuser": AuthRole.SUPERUSER,
    "superusers": AuthRole.SUPERUSER,
}


class ExternalAuthBridge:
    """Bridge between external auth providers and the local auth model.

    Manages OIDC provider configs, validates tokens (stubbed), and maps
    external group memberships to local ``AuthRole`` values.
    """

    def __init__(
        self,
        group_role_map: dict[str, AuthRole] | None = None,
    ) -> None:
        self._providers: dict[ExternalAuthProvider, OIDCConfig] = {}
        self._group_role_map = dict(group_role_map or _DEFAULT_GROUP_ROLE_MAP)

    # -- provider management -------------------------------------------

    def register_provider(self, config: OIDCConfig) -> None:
        """Register (or replace) an OIDC provider configuration."""
        self._providers[config.provider] = config

    def list_providers(self) -> list[OIDCConfig]:
        """Return all registered provider configurations."""
        return list(self._providers.values())

    # -- token validation (stub) ---------------------------------------

    def validate_token(
        self,
        provider: ExternalAuthProvider,
        token: str,
    ) -> ExternalAuthUser:
        """Validate a bearer token and return the external user.

        Raises ``ValueError`` if the provider is not registered.

        .. note::
            This is a stub implementation. A real version would verify the
            JWT signature against the provider's JWKS endpoint.
        """
        if provider not in self._providers:
            msg = f"Provider {provider!r} is not registered"
            raise ValueError(msg)

        # Stub: return a placeholder user.  Real implementation would
        # decode and verify the JWT, then extract claims.
        return ExternalAuthUser(
            provider=provider,
            external_id="stub-external-id",
            email="stub@example.com",
            name="Stub User",
        )

    # -- role mapping --------------------------------------------------

    def map_to_local_role(self, groups: tuple[str, ...] | list[str]) -> AuthRole:
        """Determine the highest-privilege local role for the given groups.

        Falls back to ``AuthRole.MEMBER`` when no group matches.
        """
        best: AuthRole = AuthRole.MEMBER
        priority = list(AuthRole)  # member < admin < superuser
        best_idx = priority.index(best)

        for group in groups:
            role = self._group_role_map.get(group.lower())
            if role is not None:
                idx = priority.index(role)
                if idx > best_idx:
                    best = role
                    best_idx = idx
        return best
