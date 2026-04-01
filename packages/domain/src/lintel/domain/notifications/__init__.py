"""Notification dispatch domain model (ARCH-004)."""

from lintel.domain.notifications.dispatcher import NotificationDispatcher
from lintel.domain.notifications.types import (
    ChannelNotifier,
    DeliveryResult,
    InMemoryEmailNotifier,
    InMemorySlackNotifier,
    InMemoryWebhookNotifier,
    InMemoryWebPushNotifier,
    NotificationMessage,
)

__all__ = [
    "ChannelNotifier",
    "DeliveryResult",
    "InMemoryEmailNotifier",
    "InMemorySlackNotifier",
    "InMemoryWebPushNotifier",
    "InMemoryWebhookNotifier",
    "NotificationDispatcher",
    "NotificationMessage",
]
