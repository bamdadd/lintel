"""Slack protocol definitions."""

from __future__ import annotations

from typing import Any, Protocol


class ChannelAdapter(Protocol):
    """Pluggable channel interface. Slack is the first implementation."""

    async def send_message(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def send_approval_request(
        self,
        channel_id: str,
        thread_ts: str,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]: ...
