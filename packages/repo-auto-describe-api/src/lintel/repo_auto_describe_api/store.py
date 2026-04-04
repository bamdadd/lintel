"""In-memory store for repository auto-descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.repo_auto_describe_api.types import RepoDescription


class InMemoryRepoDescriptionStore:
    """Simple in-memory store for repo descriptions."""

    def __init__(self) -> None:
        self._data: dict[str, RepoDescription] = {}

    async def add(self, description: RepoDescription) -> None:
        self._data[description.id] = description

    async def get(self, description_id: str) -> RepoDescription | None:
        return self._data.get(description_id)

    async def get_by_repo(self, repo_id: str) -> RepoDescription | None:
        """Return the most recent description for a repo."""
        matches = [d for d in self._data.values() if d.repo_id == repo_id]
        if not matches:
            return None
        return max(matches, key=lambda d: d.created_at)

    async def list_all(self) -> list[RepoDescription]:
        return list(self._data.values())

    async def update(self, description: RepoDescription) -> None:
        self._data[description.id] = description
