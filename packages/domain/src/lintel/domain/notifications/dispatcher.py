"""Notification dispatch service that routes messages to channel handlers."""

from __future__ import annotations

import logging
from typing import Any

from lintel.domain.notifications.types import (
    ChannelNotifier,
    DeliveryResult,
    NotificationMessage,
)
from lintel.domain.types import NotificationChannel

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Routes notification messages to the appropriate channel handler.

    Register channel-specific notifiers, then call ``dispatch`` to send a
    message through the correct handler.  If no handler is registered for the
    requested channel, a failed ``DeliveryResult`` is returned.
    """

    def __init__(self) -> None:
        self._handlers: dict[NotificationChannel, ChannelNotifier] = {}

    def register(self, channel: NotificationChannel, handler: ChannelNotifier) -> None:
        """Register a handler for a notification channel."""
        self._handlers[channel] = handler

    async def dispatch(self, message: NotificationMessage) -> DeliveryResult:
        """Dispatch a single message to the appropriate channel handler."""
        handler = self._handlers.get(message.channel)
        if handler is None:
            logger.warning("No handler registered for channel %s", message.channel)
            return DeliveryResult(
                success=False,
                channel=message.channel,
                recipient=message.recipient,
                error=f"No handler registered for channel {message.channel}",
            )
        try:
            return await handler.send(message)
        except Exception as exc:
            logger.exception("Failed to send notification via %s", message.channel)
            return DeliveryResult(
                success=False,
                channel=message.channel,
                recipient=message.recipient,
                error=str(exc),
            )

    async def dispatch_many(self, messages: list[NotificationMessage]) -> list[DeliveryResult]:
        """Dispatch multiple messages, returning results in the same order."""
        return [await self.dispatch(m) for m in messages]

    @property
    def registered_channels(self) -> list[NotificationChannel]:
        """Return the list of channels with registered handlers."""
        return list(self._handlers.keys())

    @classmethod
    def create_default(cls) -> NotificationDispatcher:
        """Create a dispatcher pre-loaded with in-memory handlers for all channels."""
        from lintel.domain.notifications.types import (
            InMemoryEmailNotifier,
            InMemorySlackNotifier,
            InMemoryWebhookNotifier,
            InMemoryWebPushNotifier,
        )

        dispatcher = cls()
        dispatcher.register(NotificationChannel.SLACK, InMemorySlackNotifier())
        dispatcher.register(NotificationChannel.EMAIL, InMemoryEmailNotifier())
        dispatcher.register(NotificationChannel.WEB_PUSH, InMemoryWebPushNotifier())
        dispatcher.register(NotificationChannel.WEBHOOK, InMemoryWebhookNotifier())
        return dispatcher

    def get_handler(self, channel: NotificationChannel) -> ChannelNotifier | None:
        """Return the handler for a channel, or None."""
        return self._handlers.get(channel)

    def handler_kwargs(self) -> dict[str, Any]:
        """Snapshot of registered handlers for debugging."""
        return {ch.value: type(h).__name__ for ch, h in self._handlers.items()}
