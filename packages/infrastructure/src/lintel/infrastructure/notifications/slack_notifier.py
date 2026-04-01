"""SlackNotifier — delivers notifications via the existing Slack adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.domain.notifications.exceptions import NotificationDeliveryError

if TYPE_CHECKING:
    from slack_sdk.web.async_client import AsyncWebClient

    from lintel.domain.types import NotificationChannel

logger = structlog.get_logger()


class SlackNotifier:
    """Implements NotificationService protocol by delegating to the Slack Web API.

    Wraps the existing slack-sdk ``AsyncWebClient`` — does not rewrite the
    Slack adapter.  The client is injected via constructor for testability.
    """

    def __init__(self, client: AsyncWebClient) -> None:
        self._client = client

    async def notify(
        self,
        recipient: str,
        channel: NotificationChannel,
        template: str,
        context: dict[str, str],
    ) -> None:
        """Post a rendered notification to a Slack channel/user.

        *recipient* is a Slack channel ID or user ID.
        *template* is a format-string rendered with *context* via ``str.format_map``.
        """
        rendered = template.format_map(context)
        try:
            result: Any = await self._client.chat_postMessage(
                channel=recipient,
                text=rendered,
            )
            logger.info(
                "slack_notification_sent",
                recipient=recipient,
                ok=getattr(result, "ok", None),
            )
        except Exception as exc:
            logger.error(
                "slack_notification_failed",
                recipient=recipient,
                error=str(exc),
            )
            msg = f"Failed to deliver Slack notification to {recipient}"
            raise NotificationDeliveryError(msg) from exc
