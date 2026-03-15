"""Repository domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RepoStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ERROR = "error"


@dataclass(frozen=True)
class Repository:
    """A registered git repository that workflows can operate on."""

    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    status: RepoStatus = RepoStatus.ACTIVE
