"""Tests for interrupt notification dispatch with connection_id routing."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from unittest.mock import AsyncMock

import pytest

from lintel.channels.registry import ChannelRegistry
from lintel.contracts.channel_type import ChannelType


class _InterruptType(Enum):
    HUMAN_APPROVAL = "human_approval"


class _FakeInterruptRequest:
    def __init__(self, run_id: str = "run-123456789012", stage: str = "review") -> None:
        self.run_id = run_id
        self.stage = stage
        self.interrupt_type = _InterruptType.HUMAN_APPROVAL
        self.deadline = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def registry() -> ChannelRegistry:
    return ChannelRegistry()


@pytest.fixture
def mock_adapter() -> AsyncMock:
    adapter = AsyncMock()
    adapter.send_message = AsyncMock(return_value={"ok": True})
    return adapter


async def test_notify_via_connection_id(registry: ChannelRegistry, mock_adapter: AsyncMock) -> None:
    from lintel.channels.interrupt_notifier import notify_interrupt

    registry.register("conn-slack-1", ChannelType.SLACK, mock_adapter)
    channels = [
        {"channel_type": "slack", "channel_id": "C123", "connection_id": "conn-slack-1"},
    ]
    await notify_interrupt(
        request=_FakeInterruptRequest(),  # type: ignore[arg-type]
        resume_url="/api/v1/resume",
        channels=channels,
        channel_registry=registry,
    )
    mock_adapter.send_message.assert_awaited_once()


async def test_notify_falls_back_to_type_when_no_connection_id(
    registry: ChannelRegistry, mock_adapter: AsyncMock
) -> None:
    from lintel.channels.interrupt_notifier import notify_interrupt

    registry.register("conn-slack-1", ChannelType.SLACK, mock_adapter)
    channels = [
        {"channel_type": "slack", "channel_id": "C123"},
    ]
    await notify_interrupt(
        request=_FakeInterruptRequest(),  # type: ignore[arg-type]
        resume_url="/api/v1/resume",
        channels=channels,
        channel_registry=registry,
    )
    mock_adapter.send_message.assert_awaited_once()


async def test_notify_connection_id_picks_correct_adapter(
    registry: ChannelRegistry,
) -> None:
    from lintel.channels.interrupt_notifier import notify_interrupt

    adapter1 = AsyncMock()
    adapter1.send_message = AsyncMock(return_value={"ok": True})
    adapter2 = AsyncMock()
    adapter2.send_message = AsyncMock(return_value={"ok": True})

    registry.register("slack-workspace-a", ChannelType.SLACK, adapter1)
    registry.register("slack-workspace-b", ChannelType.SLACK, adapter2)

    channels = [
        {
            "channel_type": "slack",
            "channel_id": "C456",
            "connection_id": "slack-workspace-b",
        },
    ]
    await notify_interrupt(
        request=_FakeInterruptRequest(),  # type: ignore[arg-type]
        resume_url="/api/v1/resume",
        channels=channels,
        channel_registry=registry,
    )
    adapter1.send_message.assert_not_awaited()
    adapter2.send_message.assert_awaited_once()


async def test_notify_unknown_connection_id_falls_back_to_type(
    registry: ChannelRegistry, mock_adapter: AsyncMock
) -> None:
    from lintel.channels.interrupt_notifier import notify_interrupt

    registry.register("conn-slack-1", ChannelType.SLACK, mock_adapter)
    channels = [
        {
            "channel_type": "slack",
            "channel_id": "C123",
            "connection_id": "nonexistent",
        },
    ]
    await notify_interrupt(
        request=_FakeInterruptRequest(),  # type: ignore[arg-type]
        resume_url="/api/v1/resume",
        channels=channels,
        channel_registry=registry,
    )
    mock_adapter.send_message.assert_awaited_once()
