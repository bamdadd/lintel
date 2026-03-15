"""Persistence domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CredentialType(StrEnum):
    SSH_KEY = "ssh_key"
    GITHUB_TOKEN = "github_token"
    AI_PROVIDER_API_KEY = "ai_provider_api_key"
    CLAUDE_CODE = "claude_code"
    TELEGRAM_BOT_TOKEN = "telegram_bot_token"


@dataclass(frozen=True)
class Credential:
    """A stored credential (SSH key or GitHub token) for repo access."""

    credential_id: str
    credential_type: CredentialType
    name: str
    repo_ids: frozenset[str] = frozenset()  # empty = applies to all repos
