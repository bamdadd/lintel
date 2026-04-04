"""Tests for ChannelRegistry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.channels.exceptions import ChannelNotRegisteredError, ConnectionNotRegisteredError
from lintel.channels.registry import ChannelRegistry, RegisteredAdapter
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


class TestConnectionIdAPI:
    """Tests for the connection_id-keyed primary API."""

    def test_register_and_get(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        assert registry.get("conn-1") is mock_adapter

    def test_get_raises_for_unknown_connection(self, registry: ChannelRegistry) -> None:
        with pytest.raises(ConnectionNotRegisteredError) as exc_info:
            registry.get("nonexistent")
        assert exc_info.value.connection_id == "nonexistent"

    def test_get_entry(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        entry = registry.get_entry("conn-1")
        assert isinstance(entry, RegisteredAdapter)
        assert entry.connection_id == "conn-1"
        assert entry.channel_type == ChannelType.SLACK
        assert entry.adapter is mock_adapter

    def test_get_entry_raises_for_unknown(self, registry: ChannelRegistry) -> None:
        with pytest.raises(ConnectionNotRegisteredError):
            registry.get_entry("nope")

    def test_unregister(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        registry.unregister("conn-1")
        assert not registry.is_connection_registered("conn-1")
        assert not registry.is_registered(ChannelType.SLACK)

    def test_unregister_noop_for_unknown(self, registry: ChannelRegistry) -> None:
        registry.unregister("nonexistent")  # should not raise

    def test_list(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        adapter2 = AsyncMock()
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        registry.register("conn-2", ChannelType.TELEGRAM, adapter2)
        entries = registry.list()
        assert len(entries) == 2
        ids = {e.connection_id for e in entries}
        assert ids == {"conn-1", "conn-2"}

    def test_is_connection_registered(
        self, registry: ChannelRegistry, mock_adapter: AsyncMock
    ) -> None:
        assert not registry.is_connection_registered("conn-1")
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        assert registry.is_connection_registered("conn-1")

    def test_overwrite_connection(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        adapter2 = AsyncMock()
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        registry.register("conn-1", ChannelType.SLACK, adapter2)
        assert registry.get("conn-1") is adapter2
        # Secondary index should not have duplicates
        assert len(registry.list_by_type(ChannelType.SLACK)) == 1


class TestChannelTypeAPI:
    """Tests for the backward-compatible ChannelType-keyed API."""

    def test_get_by_type(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        assert registry.get_by_type(ChannelType.SLACK) is mock_adapter

    def test_get_by_type_raises_for_unregistered(self, registry: ChannelRegistry) -> None:
        with pytest.raises(ChannelNotRegisteredError) as exc_info:
            registry.get_by_type(ChannelType.TELEGRAM)
        assert exc_info.value.channel_type == ChannelType.TELEGRAM

    def test_is_registered(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        assert not registry.is_registered(ChannelType.SLACK)
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        assert registry.is_registered(ChannelType.SLACK)

    def test_registered_types(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        registry.register("conn-2", ChannelType.TELEGRAM, AsyncMock())
        types = registry.registered_types()
        assert ChannelType.SLACK in types
        assert ChannelType.TELEGRAM in types

    def test_list_by_type(self, registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
        adapter2 = AsyncMock()
        registry.register("slack-1", ChannelType.SLACK, mock_adapter)
        registry.register("slack-2", ChannelType.SLACK, adapter2)
        registry.register("tg-1", ChannelType.TELEGRAM, AsyncMock())
        slack_entries = registry.list_by_type(ChannelType.SLACK)
        assert len(slack_entries) == 2
        ids = {e.connection_id for e in slack_entries}
        assert ids == {"slack-1", "slack-2"}

    def test_list_by_type_empty(self, registry: ChannelRegistry) -> None:
        assert registry.list_by_type(ChannelType.SLACK) == []

    def test_get_for_message_falls_back_to_type(
        self, registry: ChannelRegistry, mock_adapter: AsyncMock
    ) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="ts123",
            sender_id="U1",
            text="hello",
        )
        assert registry.get_for_message(msg) is mock_adapter

    def test_get_for_message_prefers_connection_id(
        self, registry: ChannelRegistry, mock_adapter: AsyncMock
    ) -> None:
        fallback = AsyncMock()
        registry.register("conn-1", ChannelType.SLACK, fallback)
        registry.register("conn-2", ChannelType.SLACK, mock_adapter)
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="ts123",
            sender_id="U1",
            text="hello",
            connection_id="conn-2",
        )
        assert registry.get_for_message(msg) is mock_adapter

    def test_get_for_message_ignores_unknown_connection_id(
        self, registry: ChannelRegistry, mock_adapter: AsyncMock
    ) -> None:
        registry.register("conn-1", ChannelType.SLACK, mock_adapter)
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="ts123",
            sender_id="U1",
            text="hello",
            connection_id="nonexistent",
        )
        # Falls back to type-based lookup
        assert registry.get_for_message(msg) is mock_adapter


class TestMultiAdapterPerType:
    """Tests for multiple adapters registered for the same channel type."""

    def test_multiple_slack_adapters(self, registry: ChannelRegistry) -> None:
        a1, a2 = AsyncMock(), AsyncMock()
        registry.register("slack-workspace-1", ChannelType.SLACK, a1)
        registry.register("slack-workspace-2", ChannelType.SLACK, a2)

        assert registry.get("slack-workspace-1") is a1
        assert registry.get("slack-workspace-2") is a2
        # get_by_type returns the first registered
        assert registry.get_by_type(ChannelType.SLACK) is a1

    def test_unregister_one_keeps_other(self, registry: ChannelRegistry) -> None:
        a1, a2 = AsyncMock(), AsyncMock()
        registry.register("s1", ChannelType.SLACK, a1)
        registry.register("s2", ChannelType.SLACK, a2)
        registry.unregister("s1")
        assert not registry.is_connection_registered("s1")
        assert registry.is_registered(ChannelType.SLACK)
        assert registry.get_by_type(ChannelType.SLACK) is a2

    def test_unregister_all_removes_type(self, registry: ChannelRegistry) -> None:
        a1, a2 = AsyncMock(), AsyncMock()
        registry.register("s1", ChannelType.SLACK, a1)
        registry.register("s2", ChannelType.SLACK, a2)
        registry.unregister("s1")
        registry.unregister("s2")
        assert not registry.is_registered(ChannelType.SLACK)
        assert registry.list_by_type(ChannelType.SLACK) == []
