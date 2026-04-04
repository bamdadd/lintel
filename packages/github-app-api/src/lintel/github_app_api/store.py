"""In-memory GitHub App installation store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.github_app_api.types import GitHubAppInstallation


class InMemoryGitHubAppInstallationStore:
    """Simple in-memory store for GitHub App installations."""

    def __init__(self) -> None:
        self._installations: dict[str, GitHubAppInstallation] = {}

    async def add(self, installation: GitHubAppInstallation) -> None:
        self._installations[installation.id] = installation

    async def get(self, installation_id: str) -> GitHubAppInstallation | None:
        return self._installations.get(installation_id)

    async def get_by_installation_id(self, installation_id: int) -> GitHubAppInstallation | None:
        """Find by GitHub's numeric installation_id."""
        for inst in self._installations.values():
            if inst.installation_id == installation_id:
                return inst
        return None

    async def list_all(self) -> list[GitHubAppInstallation]:
        return list(self._installations.values())

    async def update(self, installation: GitHubAppInstallation) -> None:
        self._installations[installation.id] = installation

    async def remove(self, installation_id: str) -> None:
        self._installations.pop(installation_id, None)
