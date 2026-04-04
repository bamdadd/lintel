"""In-memory repo description store and data models."""

from __future__ import annotations

import dataclasses
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any


@dataclasses.dataclass
class RepoDescription:
    repo_id: str = dataclasses.field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    project_id: str = ""
    description: str = ""
    languages: list[str] = dataclasses.field(default_factory=list)
    tags: list[str] = dataclasses.field(default_factory=list)
    service_type: str = ""  # e.g. "api", "frontend", "worker", "library"
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


@dataclasses.dataclass
class RepoSelection:
    repo_id: str = ""
    name: str = ""
    score: float = 0.0
    reason: str = ""


class InMemoryRepoDescriptionStore:
    """Simple in-memory store for repo descriptions."""

    def __init__(self) -> None:
        self._repos: dict[str, RepoDescription] = {}

    async def add(self, repo: RepoDescription) -> dict[str, Any]:
        if repo.repo_id in self._repos:
            msg = f"Repo {repo.repo_id} already exists"
            raise ValueError(msg)
        self._repos[repo.repo_id] = repo
        return asdict(repo)

    async def get(self, repo_id: str) -> dict[str, Any] | None:
        repo = self._repos.get(repo_id)
        if repo is None:
            return None
        return asdict(repo)

    async def list_all(self, project_id: str | None = None) -> list[dict[str, Any]]:
        repos = self._repos.values()
        if project_id:
            repos = [r for r in repos if r.project_id == project_id]
        return [asdict(r) for r in repos]

    async def remove(self, repo_id: str) -> bool:
        if repo_id not in self._repos:
            return False
        del self._repos[repo_id]
        return True

    def get_all_repos(self) -> list[RepoDescription]:
        """Return raw RepoDescription objects for the selector engine."""
        return list(self._repos.values())
