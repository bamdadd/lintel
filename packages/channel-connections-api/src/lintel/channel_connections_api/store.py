"""In-memory channel connection store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.channel_connections_api.types import ChannelConnection


class InMemoryChannelConnectionStore:
    """Simple in-memory store for channel connections."""

    def __init__(self) -> None:
        self._connections: dict[str, ChannelConnection] = {}

    async def add(self, connection: ChannelConnection) -> None:
        self._connections[connection.id] = connection

    async def get(self, connection_id: str) -> ChannelConnection | None:
        return self._connections.get(connection_id)

    async def list_all(self) -> list[ChannelConnection]:
        return list(self._connections.values())

    async def update(self, connection: ChannelConnection) -> None:
        self._connections[connection.id] = connection

    async def remove(self, connection_id: str) -> None:
        del self._connections[connection_id]
