"""Notification dispatch domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from lintel.domain.types import NotificationChannel


@dataclass(frozen=True)
class NotificationMessage:
    """A notification to be dispatched to a specific channel."""

    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of a notification delivery attempt."""

    success: bool
    channel: NotificationChannel
    recipient: str
    error: str | None = None


@runtime_checkable
class ChannelNotifier(Protocol):
    """Protocol for channel-specific notification handlers."""

    async def send(self, message: NotificationMessage) -> DeliveryResult: ...


class InMemorySlackNotifier:
    """In-memory Slack notifier for testing."""

    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(
            success=True,
            channel=NotificationChannel.SLACK,
            recipient=message.recipient,
        )


class InMemoryEmailNotifier:
    """In-memory email notifier for testing."""

    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(
            success=True,
            channel=NotificationChannel.EMAIL,
            recipient=message.recipient,
        )


class InMemoryWebPushNotifier:
    """In-memory web push notifier for testing."""

    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(
            success=True,
            channel=NotificationChannel.WEB_PUSH,
            recipient=message.recipient,
        )


class InMemoryWebhookNotifier:
    """In-memory webhook notifier for testing."""

    def __init__(self) -> None:
        self.sent: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(
            success=True,
            channel=NotificationChannel.WEBHOOK,
            recipient=message.recipient,
        )
