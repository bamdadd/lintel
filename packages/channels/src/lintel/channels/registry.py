"""ChannelRegistry — runtime registry for channel adapters.

Supports two lookup strategies:
- **by connection_id** — the primary key, allows multiple adapters per channel type
  (e.g. two Slack workspaces each with their own connection).
- **by ChannelType** — backward-compatible convenience that returns the first
  registered adapter of that type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from lintel.channels.exceptions import (
    ChannelNotRegisteredError,
    ConnectionNotRegisteredError,
)

if TYPE_CHECKING:
    from lintel.contracts.channel_adapter import ChannelAdapter
    from lintel.contracts.channel_type import ChannelType
    from lintel.contracts.inbound_message import InboundMessage

logger = structlog.get_logger()


@dataclass(frozen=True)
class RegisteredAdapter:
    """An adapter together with its connection metadata."""

    connection_id: str
    channel_type: ChannelType
    adapter: ChannelAdapter


class ChannelRegistry:
    """Maps connection_id strings to registered ChannelAdapter instances.

    Also maintains a secondary index by ChannelType so that callers that
    only know the channel type (e.g. interrupt notifier) can still resolve
    an adapter.
    """

    def __init__(self) -> None:
        self._by_connection: dict[str, RegisteredAdapter] = {}
        self._by_type: dict[ChannelType, list[str]] = {}

    # ------------------------------------------------------------------
    # connection_id-keyed API (primary)
    # ------------------------------------------------------------------

    def register(
        self,
        connection_id: str,
        channel_type: ChannelType,
        adapter: ChannelAdapter,
    ) -> None:
        """Register an adapter for a connection_id."""
        logger.info(
            "channel_adapter.registered",
            connection_id=connection_id,
            channel_type=channel_type.value,
        )
        entry = RegisteredAdapter(
            connection_id=connection_id,
            channel_type=channel_type,
            adapter=adapter,
        )
        self._by_connection[connection_id] = entry

        # Update secondary index
        if channel_type not in self._by_type:
            self._by_type[channel_type] = []
        if connection_id not in self._by_type[channel_type]:
            self._by_type[channel_type].append(connection_id)

    def get(self, connection_id: str) -> ChannelAdapter:
        """Get the adapter for a connection_id.

        Raises ConnectionNotRegisteredError if not found.
        """
        entry = self._by_connection.get(connection_id)
        if entry is None:
            raise ConnectionNotRegisteredError(connection_id)
        return entry.adapter

    def get_entry(self, connection_id: str) -> RegisteredAdapter:
        """Get the full RegisteredAdapter entry for a connection_id.

        Raises ConnectionNotRegisteredError if not found.
        """
        entry = self._by_connection.get(connection_id)
        if entry is None:
            raise ConnectionNotRegisteredError(connection_id)
        return entry

    def unregister(self, connection_id: str) -> None:
        """Remove an adapter by connection_id. No-op if not registered."""
        entry = self._by_connection.pop(connection_id, None)
        if entry is None:
            return
        type_list = self._by_type.get(entry.channel_type, [])
        if connection_id in type_list:
            type_list.remove(connection_id)
        if not type_list:
            self._by_type.pop(entry.channel_type, None)
        logger.info(
            "channel_adapter.unregistered",
            connection_id=connection_id,
            channel_type=entry.channel_type.value,
        )

    def list(self) -> list[RegisteredAdapter]:
        """Return all registered adapter entries."""
        return list(self._by_connection.values())

    def is_connection_registered(self, connection_id: str) -> bool:
        """Check if a connection_id is registered."""
        return connection_id in self._by_connection

    # ------------------------------------------------------------------
    # ChannelType-keyed API (backward-compatible convenience)
    # ------------------------------------------------------------------

    def get_by_type(self, channel_type: ChannelType) -> ChannelAdapter:
        """Get the first adapter registered for a channel type.

        Raises ChannelNotRegisteredError if none registered.
        """
        conn_ids = self._by_type.get(channel_type, [])
        if not conn_ids:
            raise ChannelNotRegisteredError(channel_type)
        return self._by_connection[conn_ids[0]].adapter

    def is_registered(self, channel_type: ChannelType) -> bool:
        """Check if any adapter is registered for a channel type."""
        return bool(self._by_type.get(channel_type))

    def registered_types(self) -> list[ChannelType]:
        """Return list of all channel types that have at least one adapter."""
        return list(self._by_type.keys())

    def list_by_type(self, channel_type: ChannelType) -> list[RegisteredAdapter]:
        """Return all adapters registered for a given channel type."""
        conn_ids = self._by_type.get(channel_type, [])
        return [self._by_connection[cid] for cid in conn_ids]

    def get_for_message(self, message: InboundMessage) -> ChannelAdapter:
        """Get the appropriate adapter for an inbound message."""
        return self.get_by_type(message.channel_type)
