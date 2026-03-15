"""Channel registry exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.channel_type import ChannelType


class ChannelNotRegisteredError(Exception):
    """Raised when no adapter is registered for a given channel type."""

    def __init__(self, channel_type: ChannelType) -> None:
        self.channel_type = channel_type
        super().__init__(f"No adapter registered for channel type: {channel_type.value}")
