"""Sandbox credential domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class SandboxCredentialType(StrEnum):
    GITHUB_TOKEN = "github_token"
    API_KEY = "api_key"
    DB_PASSWORD = "db_password"


class SandboxCredentialStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class SandboxCredential:
    """An ephemeral credential scoped to a sandbox session."""

    id: str
    sandbox_id: str
    credential_type: SandboxCredentialType
    name: str
    scopes: tuple[str, ...] = ()
    status: SandboxCredentialStatus = SandboxCredentialStatus.ACTIVE
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(UTC) + timedelta(hours=1),
    )
    revoked_at: datetime | None = None
