"""In-memory channel adapter registry store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.channel_adapter_registry_api.types import ChannelAdapter


class InMemoryChannelAdapterStore:
    """Simple in-memory store for channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    async def add(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.id] = adapter

    async def get(self, adapter_id: str) -> ChannelAdapter | None:
        return self._adapters.get(adapter_id)

    async def list_all(self) -> list[ChannelAdapter]:
        return list(self._adapters.values())

    async def update(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.id] = adapter

    async def remove(self, adapter_id: str) -> None:
        del self._adapters[adapter_id]

    async def find_by_bot_and_connection(
        self,
        bot_id: str,
        connection_id: str,
    ) -> ChannelAdapter | None:
        """Find adapter by bot_id + connection_id composite key."""
        for adapter in self._adapters.values():
            if adapter.bot_id == bot_id and adapter.connection_id == connection_id:
                return adapter
        return None

    async def route(
        self,
        bot_id: str,
        channel_type: str,
    ) -> ChannelAdapter | None:
        """Find the best adapter for a given bot and channel type.

        Returns the highest-priority enabled adapter matching the criteria.
        """
        candidates = [
            a
            for a in self._adapters.values()
            if a.bot_id == bot_id and a.channel_type == channel_type and a.enabled
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda a: a.priority, reverse=True)
        return candidates[0]
