"""Channel expansion — multi-channel communication adapters (INT-5)."""

from lintel.domain.channels.factory import ChannelAdapter, ChannelFactory
from lintel.domain.channels.types import ChannelConfig, ChannelMessage, ChannelType

__all__ = [
    "ChannelAdapter",
    "ChannelConfig",
    "ChannelFactory",
    "ChannelMessage",
    "ChannelType",
]
