"""Repository-related commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.repos.types import RepoStatus


@dataclass(frozen=True)
class RegisterRepository:
    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class UpdateRepository:
    repo_id: str
    name: str | None = None
    default_branch: str | None = None
    owner: str | None = None
    status: RepoStatus | None = None
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RemoveRepository:
    repo_id: str
    correlation_id: UUID = field(default_factory=uuid4)
