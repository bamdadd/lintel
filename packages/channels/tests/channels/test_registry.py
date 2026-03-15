"""Tests for ChannelRegistry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.channels.exceptions import ChannelNotRegisteredError
from lintel.channels.registry import ChannelRegistry
from lintel.contracts.channel_type import ChannelType
from lintel.contracts.inbound_message import InboundMessage


@pytest.fixture
def registry() -> ChannelRegistry:
    return ChannelRegistry()


@pytest.fixture
def mock_adapter() -> AsyncMock:
    adapter = AsyncMock()
    adapter.send_message = AsyncMock(return_value={"ok": True})
    adapter.send_reply = AsyncMock(return_value={"ok": True})
    adapter.send_approval_request = AsyncMock(return_value={"ok": True})
    return adapter


class TestChannelRegistry:
    def test_register_and_get(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register(ChannelType.SLACK, mock_adapter)
        assert registry.get(ChannelType.SLACK) is mock_adapter

    def test_raises_for_unregistered_type(self, registry: ChannelRegistry) -> None:
        with pytest.raises(ChannelNotRegisteredError) as exc_info:
            registry.get(ChannelType.TELEGRAM)
        assert exc_info.value.channel_type == ChannelType.TELEGRAM

    def test_is_registered(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        assert not registry.is_registered(ChannelType.SLACK)
        registry.register(ChannelType.SLACK, mock_adapter)
        assert registry.is_registered(ChannelType.SLACK)

    def test_registered_types(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register(ChannelType.SLACK, mock_adapter)
        registry.register(ChannelType.TELEGRAM, AsyncMock())
        types = registry.registered_types()
        assert ChannelType.SLACK in types
        assert ChannelType.TELEGRAM in types

    def test_get_for_message(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register(ChannelType.SLACK, mock_adapter)
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="ts123",
            sender_id="U1",
            text="hello",
        )
        assert registry.get_for_message(msg) is mock_adapter

    def test_overwrite_registration(
        self, registry: ChannelRegistry, mock_adapter: AsyncMock
    ) -> None:
        adapter2 = AsyncMock()
        registry.register(ChannelType.SLACK, mock_adapter)
        registry.register(ChannelType.SLACK, adapter2)
        assert registry.get(ChannelType.SLACK) is adapter2
