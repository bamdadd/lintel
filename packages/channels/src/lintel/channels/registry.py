"""ChannelRegistry — runtime registry mapping ChannelType to ChannelAdapter instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lintel.channels.exceptions import ChannelNotRegisteredError

if TYPE_CHECKING:
    from lintel.contracts.channel_adapter import ChannelAdapter
    from lintel.contracts.channel_type import ChannelType
    from lintel.contracts.inbound_message import InboundMessage

logger = structlog.get_logger()


class ChannelRegistry:
    """Maps ChannelType values to registered ChannelAdapter instances.

    Acts as the single point of indirection so the coordination layer
    never needs to know which specific adapter is handling a message.
    """

    def __init__(self) -> None:
        self._adapters: dict[ChannelType, ChannelAdapter] = {}

    def register(self, channel_type: ChannelType, adapter: ChannelAdapter) -> None:
        """Register an adapter for a channel type."""
        logger.info("channel_adapter.registered", channel_type=channel_type.value)
        self._adapters[channel_type] = adapter

    def get(self, channel_type: ChannelType) -> ChannelAdapter:
        """Get the adapter for a channel type.

        Raises ChannelNotRegisteredError if no adapter is registered.
        """
        adapter = self._adapters.get(channel_type)
        if adapter is None:
            raise ChannelNotRegisteredError(channel_type)
        return adapter

    def is_registered(self, channel_type: ChannelType) -> bool:
        """Check if an adapter is registered for a channel type."""
        return channel_type in self._adapters

    def registered_types(self) -> list[ChannelType]:
        """Return list of all registered channel types."""
        return list(self._adapters.keys())

    def get_for_message(self, message: InboundMessage) -> ChannelAdapter:
        """Get the appropriate adapter for an inbound message."""
        return self.get(message.channel_type)
