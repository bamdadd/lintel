"""Tests for TelegramChannelAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lintel.contracts.channel_type import ChannelType
from lintel.contracts.types import ThreadRef
from lintel.telegram.adapter import TelegramChannelAdapter


@pytest.fixture
def adapter() -> TelegramChannelAdapter:
    return TelegramChannelAdapter(bot_token="test-token", webhook_secret="test-secret")


class TestTelegramChannelAdapter:
    def test_webhook_secret(self, adapter: TelegramChannelAdapter) -> None:
        assert adapter.webhook_secret == "test-secret"

    def test_make_thread_ref(self, adapter: TelegramChannelAdapter) -> None:
        ref = adapter.make_thread_ref("12345", "67890")
        assert ref.channel_type == ChannelType.TELEGRAM
        assert ref.channel_id == "12345"
        assert ref.thread_ts == "67890"
        assert ref.workspace_id == "telegram"

    async def test_send_message(self, adapter: TelegramChannelAdapter) -> None:
        thread_ref = ThreadRef(
            workspace_id="telegram",
            channel_id="12345",
            thread_ts="12345",
            channel_type=ChannelType.TELEGRAM,
        )
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await adapter.send_message(thread_ref, "Hello!")
            assert result["message_id"] == 1
            mock_client.post.assert_called_once()

    async def test_send_approval_request(self, adapter: TelegramChannelAdapter) -> None:
        thread_ref = ThreadRef(
            workspace_id="telegram",
            channel_id="12345",
            thread_ts="12345",
            channel_type=ChannelType.TELEGRAM,
        )
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 2}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await adapter.send_approval_request(
                thread_ref, "spec_review", "Review spec", "cb-1"
            )
            assert result["message_id"] == 2
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1].get(
                "json", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
            )
            if isinstance(payload, dict):
                assert "reply_markup" in payload
