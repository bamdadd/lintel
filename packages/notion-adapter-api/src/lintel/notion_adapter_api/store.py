"""In-memory store for Notion connection configs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class NotionConnection:
    """A configured Notion integration connection."""

    connection_id: str
    project_id: str
    database_id: str
    api_key: str
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )
    last_synced_at: str | None = None


class InMemoryNotionConnectionStore:
    """Simple in-memory store for Notion connections."""

    def __init__(self) -> None:
        self._connections: dict[str, NotionConnection] = {}

    async def add(self, connection: NotionConnection) -> None:
        self._connections[connection.connection_id] = connection

    async def get(self, connection_id: str) -> NotionConnection | None:
        return self._connections.get(connection_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[NotionConnection]:
        items = list(self._connections.values())
        if project_id is not None:
            items = [c for c in items if c.project_id == project_id]
        return items

    async def update(self, connection: NotionConnection) -> None:
        if connection.connection_id not in self._connections:
            msg = f"Connection {connection.connection_id} not found"
            raise KeyError(msg)
        self._connections[connection.connection_id] = connection

    async def remove(self, connection_id: str) -> None:
        if connection_id not in self._connections:
            msg = f"Connection {connection_id} not found"
            raise KeyError(msg)
        del self._connections[connection_id]
