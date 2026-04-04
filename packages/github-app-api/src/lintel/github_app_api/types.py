"""GitHub App installation domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class GitHubAppInstallation:
    """A GitHub App installation record."""

    id: str
    installation_id: int
    account_login: str  # GitHub org or user login
    account_type: str = "Organization"  # Organization or User
    access_token: str = ""
    token_expires_at: str = ""
    permissions: dict[str, str] = field(default_factory=dict)
    repository_selection: str = "all"  # all or selected
    suspended: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
