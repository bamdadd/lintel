"""EmailNotifier — stub implementation for future SMTP/SES delivery."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.domain.types import NotificationChannel

logger = structlog.get_logger()


class EmailNotifier:
    """No-op stub that satisfies the NotificationService protocol.

    Logs a warning and returns without raising, so the rule engine
    functions without breaking when email channels are configured.
    Replace with a real SMTP/SES implementation when ready.
    """

    async def notify(
        self,
        recipient: str,
        channel: NotificationChannel,
        template: str,
        context: dict[str, str],
    ) -> None:
        logger.warning(
            "email_notifier_not_implemented",
            channel=str(channel),
            recipient=recipient,
        )
