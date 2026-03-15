"""TelegramChannelAdapter — implements ChannelAdapter protocol for Telegram."""

from __future__ import annotations

import contextlib
from typing import Any

import structlog

from lintel.contracts.channel_type import ChannelType
from lintel.contracts.types import ThreadRef
from lintel.telegram.keyboards import build_approval_keyboard

logger = structlog.get_logger()


class TelegramChannelAdapter:
    """Implements ChannelAdapter protocol using Telegram Bot API via httpx.

    Uses direct HTTP calls to the Telegram Bot API rather than aiogram's
    Bot class to keep the dependency lightweight and testable.
    """

    def __init__(self, bot_token: str, webhook_secret: str = "") -> None:
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        self._api_base = f"https://api.telegram.org/bot{bot_token}"
        self._bot_username: str = ""

    @property
    def bot_username(self) -> str:
        """Return the cached bot username."""
        return self._bot_username

    @property
    def webhook_secret(self) -> str:
        """Return the webhook secret for verification."""
        return self._webhook_secret

    async def get_me(self) -> dict[str, Any]:
        """Call Telegram getMe to verify the bot token and get bot info."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._api_base}/getMe")
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                self._bot_username = result["result"].get("username", "")
            result_data: dict[str, Any] = result.get("result", {})
            return result_data

    async def setup_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Register webhook URL with Telegram's setWebhook API."""
        import httpx

        params: dict[str, Any] = {"url": webhook_url}
        if self._webhook_secret:
            params["secret_token"] = self._webhook_secret

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self._api_base}/setWebhook", json=params)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            logger.info("telegram.webhook_set", url=webhook_url, ok=result.get("ok"))
            return result

    async def send_message(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Send a message to a Telegram chat."""
        import httpx

        payload: dict[str, Any] = {
            "chat_id": thread_ref.channel_id,
            "text": text,
        }
        # If thread_ts looks like a forum topic thread_id, include it
        if thread_ref.thread_ts and thread_ref.thread_ts != thread_ref.channel_id:
            with contextlib.suppress(ValueError):
                payload["message_thread_id"] = int(thread_ref.thread_ts)

        reply_markup = kwargs.get("reply_markup")
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self._api_base}/sendMessage", json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json().get("result", {})
            return data

    async def send_reply(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Send a reply — same as send_message for Telegram."""
        return await self.send_message(thread_ref, text, **kwargs)

    async def send_approval_request(
        self,
        thread_ref: ThreadRef,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]:
        """Send an approval request with inline keyboard buttons."""
        keyboard = build_approval_keyboard(callback_id)
        text = f"*Approval Required: {gate_type}*\n\n{summary}"
        return await self.send_message(
            thread_ref,
            text,
            reply_markup=keyboard,
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> dict[str, Any]:
        """Answer a callback query to dismiss the loading indicator."""
        import httpx

        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self._api_base}/answerCallbackQuery", json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json().get("result", {})
            return data

    def make_thread_ref(
        self,
        chat_id: str,
        thread_id: str,
    ) -> ThreadRef:
        """Create a ThreadRef for a Telegram conversation."""
        return ThreadRef(
            workspace_id="telegram",
            channel_id=chat_id,
            thread_ts=thread_id,
            channel_type=ChannelType.TELEGRAM,
        )
