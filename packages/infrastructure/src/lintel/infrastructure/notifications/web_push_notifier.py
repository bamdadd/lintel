"""WebPushNotifier — stub implementation for future browser push notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.domain.types import NotificationChannel

logger = structlog.get_logger()


class WebPushNotifier:
    """No-op stub that satisfies the NotificationService protocol.

    Logs a warning and returns without raising, so the rule engine
    functions without breaking when web-push channels are configured.
    Replace with a real Web Push implementation when ready.
    """

    async def notify(
        self,
        recipient: str,
        channel: NotificationChannel,
        template: str,
        context: dict[str, str],
    ) -> None:
        logger.warning(
            "web_push_notifier_not_implemented",
            channel=str(channel),
            recipient=recipient,
        )
