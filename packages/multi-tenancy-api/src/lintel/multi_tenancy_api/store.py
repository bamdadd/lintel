"""In-memory workspace store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Workspace:
    """A tenant workspace."""

    workspace_id: str
    name: str
    slug: str
    owner_user_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )


class InMemoryWorkspaceStore:
    """Simple in-memory store for workspaces."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        self._by_slug: dict[str, str] = {}  # slug → workspace_id

    async def add(self, workspace: Workspace) -> None:
        self._workspaces[workspace.workspace_id] = workspace
        self._by_slug[workspace.slug] = workspace.workspace_id

    async def get(self, workspace_id: str) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    async def get_by_slug(self, slug: str) -> Workspace | None:
        ws_id = self._by_slug.get(slug)
        if ws_id is None:
            return None
        return self._workspaces.get(ws_id)

    async def list_all(self) -> list[Workspace]:
        return list(self._workspaces.values())

    async def list_by_owner(self, owner_user_id: str) -> list[Workspace]:
        return [w for w in self._workspaces.values() if w.owner_user_id == owner_user_id]
