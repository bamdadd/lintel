"""In-memory repo description store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoDescription:
    """A project-scoped description for a repository."""

    project_id: str
    repo_id: str
    description: str = ""


class InMemoryRepoDescriptionStore:
    """Simple in-memory store keyed by (project_id, repo_id)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], RepoDescription] = {}

    async def put(self, entry: RepoDescription) -> None:
        self._data[(entry.project_id, entry.repo_id)] = entry

    async def get(self, project_id: str, repo_id: str) -> RepoDescription | None:
        return self._data.get((project_id, repo_id))

    async def list_by_project(self, project_id: str) -> list[RepoDescription]:
        return [v for k, v in self._data.items() if k[0] == project_id]

    async def remove(self, project_id: str, repo_id: str) -> None:
        self._data.pop((project_id, repo_id), None)
