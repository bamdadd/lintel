"""Auth domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AuthRole(StrEnum):
    """Role for authentication / authorization."""

    MEMBER = "member"
    ADMIN = "admin"
    SUPERUSER = "superuser"


@dataclass(frozen=True)
class AuthUser:
    """User with authentication credentials.

    Extends the concept of the domain ``User`` with a hashed password and
    an auth-specific role.
    """

    user_id: str
    email: str
    name: str
    hashed_password: str
    role: AuthRole = AuthRole.MEMBER
    slack_user_id: str = ""


@dataclass(frozen=True)
class AuthSession:
    """Persistent login session.

    Created on login, invalidated on logout or explicit revocation.
    The refresh_token_jti ties the session to a specific refresh token
    so revoking a session also invalidates outstanding refresh tokens.
    """

    session_id: str
    user_id: str
    refresh_token_jti: str
    created_at: str  # ISO-8601
    expires_at: str  # ISO-8601
    user_agent: str = ""
    ip_address: str = ""
    revoked: bool = False
    revoked_at: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class MFAMethod(StrEnum):
    """Supported MFA methods."""

    TOTP = "totp"
    WEBAUTHN = "webauthn"


@dataclass(frozen=True)
class MFAConfig:
    """MFA configuration for a user.

    Each user may have multiple MFA methods configured.
    """

    user_id: str
    method: MFAMethod
    enabled: bool = False
    totp_secret: str = ""
    webauthn_credential_id: str = ""
    created_at: str = ""
