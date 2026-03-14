"""SlackChannelAdapter -- implements ChannelAdapter protocol via slack-bolt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from slack_sdk.web.async_client import AsyncWebClient

logger = structlog.get_logger()


class SlackChannelAdapter:
    """Implements ChannelAdapter protocol with Slack Web API."""

    def __init__(self, client: AsyncWebClient) -> None:
        self._client = client

    async def send_message(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await self._client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
        return dict(result)  # type: ignore[call-overload, no-any-return]

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await self._client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=text,
            blocks=blocks,
        )
        return dict(result)  # type: ignore[call-overload, no-any-return]

    async def send_approval_request(
        self,
        channel_id: str,
        thread_ts: str,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]:
        from lintel.slack.block_kit import (
            build_approval_blocks,
        )

        blocks = build_approval_blocks(gate_type, summary, callback_id)
        return await self.send_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=f"Approval required: {gate_type}",
            blocks=blocks,
        )
