"""Channels package — runtime registry for channel adapters."""

from lintel.channels.exceptions import ChannelNotRegisteredError, ConnectionNotRegisteredError
from lintel.channels.registry import ChannelRegistry, RegisteredAdapter

__all__ = [
    "ChannelNotRegisteredError",
    "ChannelRegistry",
    "ConnectionNotRegisteredError",
    "RegisteredAdapter",
]
