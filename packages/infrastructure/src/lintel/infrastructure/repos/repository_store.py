"""In-memory implementation of RepositoryStore protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.repos.types import Repository


class InMemoryRepositoryStore:
    """Simple in-memory store for registered repositories."""

    def __init__(self) -> None:
        self._repos: dict[str, Repository] = {}

    async def add(self, repository: Repository) -> None:
        if repository.repo_id in self._repos:
            msg = f"Repository {repository.repo_id} already exists"
            raise ValueError(msg)
        self._repos[repository.repo_id] = repository

    async def get(self, repo_id: str) -> Repository | None:
        return self._repos.get(repo_id)

    async def get_by_url(self, url: str) -> Repository | None:
        for repo in self._repos.values():
            if repo.url == url:
                return repo
        return None

    async def list_all(self) -> list[Repository]:
        return list(self._repos.values())

    async def update(self, repository: Repository) -> None:
        if repository.repo_id not in self._repos:
            msg = f"Repository {repository.repo_id} not found"
            raise KeyError(msg)
        self._repos[repository.repo_id] = repository

    async def remove(self, repo_id: str) -> None:
        if repo_id not in self._repos:
            msg = f"Repository {repo_id} not found"
            raise KeyError(msg)
        del self._repos[repo_id]
