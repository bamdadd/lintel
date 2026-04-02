"""Tests for channel factory and domain types."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lintel.domain.channels.factory import ChannelAdapter, ChannelFactory
from lintel.domain.channels.types import ChannelConfig, ChannelMessage, ChannelType


class FakeSlackAdapter:
    """Fake Slack adapter for testing."""

    async def send_message(self, channel_id: str, content: str) -> ChannelMessage:
        return ChannelMessage(
            channel_type=ChannelType.SLACK,
            channel_id=channel_id,
            sender_id="bot",
            content=content,
            timestamp=datetime.now(tz=UTC),
        )

    async def receive_messages(self, channel_id: str, limit: int = 50) -> list[ChannelMessage]:
        return []

    async def get_channel_info(self, channel_id: str) -> dict[str, object]:
        return {"name": "general", "channel_id": channel_id}


class FakeDiscordAdapter:
    """Fake Discord adapter for testing."""

    async def send_message(self, channel_id: str, content: str) -> ChannelMessage:
        return ChannelMessage(
            channel_type=ChannelType.DISCORD,
            channel_id=channel_id,
            sender_id="bot",
            content=content,
            timestamp=datetime.now(tz=UTC),
        )

    async def receive_messages(self, channel_id: str, limit: int = 50) -> list[ChannelMessage]:
        return []

    async def get_channel_info(self, channel_id: str) -> dict[str, object]:
        return {"name": "general", "channel_id": channel_id}


class TestChannelType:
    def test_all_channel_types_exist(self) -> None:
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.TELEGRAM.value == "telegram"
        assert ChannelType.DISCORD.value == "discord"
        assert ChannelType.TEAMS.value == "teams"
        assert ChannelType.WEB.value == "web"
        assert ChannelType.EMAIL.value == "email"

    def test_channel_type_count(self) -> None:
        assert len(ChannelType) == 6


class TestChannelMessage:
    def test_frozen(self) -> None:
        msg = ChannelMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            sender_id="U456",
            content="hello",
            timestamp=datetime.now(tz=UTC),
        )
        with pytest.raises(AttributeError):
            msg.content = "changed"  # type: ignore[misc]

    def test_metadata_default(self) -> None:
        msg = ChannelMessage(
            channel_type=ChannelType.WEB,
            channel_id="web-1",
            sender_id="u1",
            content="hi",
            timestamp=datetime.now(tz=UTC),
        )
        assert msg.metadata == {}


class TestChannelConfig:
    def test_frozen(self) -> None:
        config = ChannelConfig(channel_type=ChannelType.DISCORD, channel_id="guild-1")
        with pytest.raises(AttributeError):
            config.channel_id = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        config = ChannelConfig(channel_type=ChannelType.TEAMS, channel_id="t-1")
        assert config.credentials == {}
        assert config.settings == {}


class TestChannelFactory:
    def test_register_and_create(self) -> None:
        factory = ChannelFactory()
        factory.register_adapter(ChannelType.SLACK, FakeSlackAdapter)  # type: ignore[arg-type]
        config = ChannelConfig(channel_type=ChannelType.SLACK, channel_id="C1")
        adapter = factory.create_adapter(config)
        assert isinstance(adapter, FakeSlackAdapter)

    def test_create_unregistered_raises(self) -> None:
        factory = ChannelFactory()
        config = ChannelConfig(channel_type=ChannelType.TEAMS, channel_id="t-1")
        with pytest.raises(ValueError, match="No adapter registered"):
            factory.create_adapter(config)

    def test_list_supported_types(self) -> None:
        factory = ChannelFactory()
        factory.register_adapter(ChannelType.DISCORD, FakeDiscordAdapter)  # type: ignore[arg-type]
        factory.register_adapter(ChannelType.SLACK, FakeSlackAdapter)  # type: ignore[arg-type]
        supported = factory.list_supported_types()
        assert supported == [ChannelType.DISCORD, ChannelType.SLACK]

    def test_list_supported_types_empty(self) -> None:
        factory = ChannelFactory()
        assert factory.list_supported_types() == []

    def test_adapter_protocol_satisfied(self) -> None:
        assert isinstance(FakeSlackAdapter(), ChannelAdapter)

    async def test_send_message(self) -> None:
        factory = ChannelFactory()
        factory.register_adapter(ChannelType.SLACK, FakeSlackAdapter)  # type: ignore[arg-type]
        config = ChannelConfig(channel_type=ChannelType.SLACK, channel_id="C1")
        adapter = factory.create_adapter(config)
        msg = await adapter.send_message("C1", "hello")
        assert msg.content == "hello"
        assert msg.channel_type == ChannelType.SLACK

    async def test_receive_messages(self) -> None:
        factory = ChannelFactory()
        factory.register_adapter(ChannelType.SLACK, FakeSlackAdapter)  # type: ignore[arg-type]
        config = ChannelConfig(channel_type=ChannelType.SLACK, channel_id="C1")
        adapter = factory.create_adapter(config)
        messages = await adapter.receive_messages("C1")
        assert messages == []

    async def test_get_channel_info(self) -> None:
        factory = ChannelFactory()
        factory.register_adapter(ChannelType.SLACK, FakeSlackAdapter)  # type: ignore[arg-type]
        config = ChannelConfig(channel_type=ChannelType.SLACK, channel_id="C1")
        adapter = factory.create_adapter(config)
        info = await adapter.get_channel_info("C1")
        assert info["channel_id"] == "C1"
