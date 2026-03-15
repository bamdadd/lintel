"""SlackChannelAdapter -- implements ChannelAdapter protocol via slack-bolt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.channel_type import ChannelType

if TYPE_CHECKING:
    from slack_sdk.web.async_client import AsyncWebClient

    from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()


class SlackChannelAdapter:
    """Implements ChannelAdapter protocol with Slack Web API.

    Supports both the legacy Slack-specific interface (channel_id, thread_ts)
    and the new generic ChannelAdapter protocol (ThreadRef-based).
    """

    channel_type = ChannelType.SLACK

    def __init__(self, client: AsyncWebClient) -> None:
        self._client = client

    # --- Generic ChannelAdapter protocol methods ---

    async def send_message(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        blocks: list[dict[str, Any]] | None = kwargs.get("blocks")  # type: ignore[assignment]
        return await self.post_message(
            channel_id=thread_ref.channel_id,
            thread_ts=thread_ref.thread_ts,
            text=text,
            blocks=blocks,
        )

    async def send_reply(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        return await self.send_message(thread_ref, text, **kwargs)

    async def send_approval_request(
        self,
        thread_ref: ThreadRef,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]:
        from lintel.slack.block_kit import build_approval_blocks

        blocks = build_approval_blocks(gate_type, summary, callback_id)
        return await self.post_message(
            channel_id=thread_ref.channel_id,
            thread_ts=thread_ref.thread_ts,
            text=f"Approval required: {gate_type}",
            blocks=blocks,
        )

    # --- Slack-specific methods (used by existing code) ---

    async def post_message(
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

    async def post_approval_request(
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
        return await self.post_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=f"Approval required: {gate_type}",
            blocks=blocks,
        )
