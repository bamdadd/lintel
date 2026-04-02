"""Channel adapter factory for multi-channel communication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from lintel.domain.channels.types import ChannelConfig, ChannelMessage, ChannelType


@runtime_checkable
class ChannelAdapter(Protocol):
    """Protocol for channel-specific communication adapters."""

    async def send_message(self, channel_id: str, content: str) -> ChannelMessage: ...

    async def receive_messages(self, channel_id: str, limit: int = 50) -> list[ChannelMessage]: ...

    async def get_channel_info(self, channel_id: str) -> dict[str, object]: ...


class ChannelFactory:
    """Registry and factory for channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[ChannelType, type[ChannelAdapter]] = {}

    def register_adapter(
        self, channel_type: ChannelType, adapter_cls: type[ChannelAdapter]
    ) -> None:
        """Register an adapter class for a channel type."""
        self._adapters[channel_type] = adapter_cls

    def create_adapter(self, config: ChannelConfig) -> ChannelAdapter:
        """Create an adapter instance from config.

        Raises:
            ValueError: If the channel type has no registered adapter.
        """
        adapter_cls = self._adapters.get(config.channel_type)
        if adapter_cls is None:
            msg = f"No adapter registered for channel type: {config.channel_type.value}"
            raise ValueError(msg)
        return adapter_cls()

    def list_supported_types(self) -> list[ChannelType]:
        """Return all channel types with registered adapters."""
        return sorted(self._adapters.keys(), key=lambda ct: ct.value)
