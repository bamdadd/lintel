"""Channels package — runtime registry for channel adapters."""

from lintel.channels.exceptions import ChannelNotRegisteredError
from lintel.channels.registry import ChannelRegistry

__all__ = [
    "ChannelNotRegisteredError",
    "ChannelRegistry",
]
