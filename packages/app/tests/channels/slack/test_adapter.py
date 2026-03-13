"""Tests for SlackChannelAdapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from lintel.infrastructure.channels.slack.adapter import SlackChannelAdapter


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1234567890.123456"}
    client.chat_update.return_value = {"ok": True, "ts": "1234567890.123456"}
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> SlackChannelAdapter:
    return SlackChannelAdapter(client=mock_client)


class TestSendMessage:
    async def test_sends_text_message(
        self,
        adapter: SlackChannelAdapter,
        mock_client: AsyncMock,
    ) -> None:
        result = await adapter.send_message("C123", "1234.0", "hello")
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123",
            thread_ts="1234.0",
            text="hello",
            blocks=None,
        )
        assert result["ok"] is True

    async def test_sends_message_with_blocks(
        self,
        adapter: SlackChannelAdapter,
        mock_client: AsyncMock,
    ) -> None:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "hi"}},
        ]
        await adapter.send_message("C123", "1234.0", "hello", blocks=blocks)
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C123",
            thread_ts="1234.0",
            text="hello",
            blocks=blocks,
        )


class TestUpdateMessage:
    async def test_updates_message(
        self,
        adapter: SlackChannelAdapter,
        mock_client: AsyncMock,
    ) -> None:
        result = await adapter.update_message("C123", "1234.0", "updated")
        mock_client.chat_update.assert_called_once_with(
            channel="C123",
            ts="1234.0",
            text="updated",
            blocks=None,
        )
        assert result["ok"] is True


class TestSendApprovalRequest:
    async def test_sends_approval_with_blocks(
        self,
        adapter: SlackChannelAdapter,
        mock_client: AsyncMock,
    ) -> None:
        result = await adapter.send_approval_request(
            channel_id="C123",
            thread_ts="1234.0",
            gate_type="spec_approval",
            summary="Review the spec",
            callback_id="cb-123",
        )
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args.kwargs
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["thread_ts"] == "1234.0"
        assert call_kwargs["blocks"] is not None
        assert len(call_kwargs["blocks"]) == 4
        assert result["ok"] is True
