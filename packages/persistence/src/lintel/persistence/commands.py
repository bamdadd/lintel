"""Persistence command schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.persistence.types import CredentialType


@dataclass(frozen=True)
class StoreCredential:
    credential_id: str
    credential_type: CredentialType
    name: str
    secret: str  # the actual key/token value (encrypted at rest)
    repo_ids: list[str] = field(default_factory=list)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RevokeCredential:
    credential_id: str
    correlation_id: UUID = field(default_factory=uuid4)
