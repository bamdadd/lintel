"""In-memory stores for Jira adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.jira_adapter_api.types import JiraConnection, SyncRecord


class InMemoryJiraConnectionStore:
    """Simple in-memory store for Jira connections."""

    def __init__(self) -> None:
        self._items: dict[str, JiraConnection] = {}

    async def add(self, item: JiraConnection) -> None:
        self._items[item.connection_id] = item

    async def get(self, connection_id: str) -> JiraConnection | None:
        return self._items.get(connection_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[JiraConnection]:
        items = list(self._items.values())
        if project_id is not None:
            items = [c for c in items if c.project_id == project_id]
        return items

    async def remove(self, connection_id: str) -> None:
        self._items.pop(connection_id, None)


class InMemorySyncRecordStore:
    """Simple in-memory store for sync records."""

    def __init__(self) -> None:
        self._items: dict[str, SyncRecord] = {}

    async def add(self, item: SyncRecord) -> None:
        self._items[item.sync_id] = item

    async def get(self, sync_id: str) -> SyncRecord | None:
        return self._items.get(sync_id)

    async def update(self, item: SyncRecord) -> None:
        self._items[item.sync_id] = item

    async def list_by_connection(self, connection_id: str) -> list[SyncRecord]:
        return [r for r in self._items.values() if r.connection_id == connection_id]
