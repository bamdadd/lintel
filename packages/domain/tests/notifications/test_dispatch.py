"""Tests for the notification dispatch service (ARCH-004)."""

from lintel.domain.notifications import (
    ChannelNotifier,
    DeliveryResult,
    InMemoryEmailNotifier,
    InMemorySlackNotifier,
    InMemoryWebhookNotifier,
    InMemoryWebPushNotifier,
    NotificationDispatcher,
    NotificationMessage,
)
from lintel.domain.types import NotificationChannel


def _msg(
    channel: NotificationChannel = NotificationChannel.SLACK,
    recipient: str = "user@example.com",
    subject: str = "Test",
    body: str = "Hello",
) -> NotificationMessage:
    return NotificationMessage(channel=channel, recipient=recipient, subject=subject, body=body)


# --- NotificationMessage ---


class TestNotificationMessage:
    def test_frozen(self) -> None:
        msg = _msg()
        assert msg.channel == NotificationChannel.SLACK
        assert msg.metadata == {}

    def test_with_metadata(self) -> None:
        msg = NotificationMessage(
            channel=NotificationChannel.EMAIL,
            recipient="a@b.com",
            subject="s",
            body="b",
            metadata={"priority": "high"},
        )
        assert msg.metadata["priority"] == "high"


# --- In-memory notifiers ---


class TestInMemoryNotifiers:
    async def test_slack_notifier(self) -> None:
        notifier = InMemorySlackNotifier()
        result = await notifier.send(_msg())
        assert result.success is True
        assert result.channel == NotificationChannel.SLACK
        assert len(notifier.sent) == 1

    async def test_email_notifier(self) -> None:
        notifier = InMemoryEmailNotifier()
        result = await notifier.send(_msg(channel=NotificationChannel.EMAIL))
        assert result.success is True
        assert result.channel == NotificationChannel.EMAIL

    async def test_web_push_notifier(self) -> None:
        notifier = InMemoryWebPushNotifier()
        result = await notifier.send(_msg(channel=NotificationChannel.WEB_PUSH))
        assert result.success is True
        assert result.channel == NotificationChannel.WEB_PUSH

    async def test_webhook_notifier(self) -> None:
        notifier = InMemoryWebhookNotifier()
        result = await notifier.send(_msg(channel=NotificationChannel.WEBHOOK))
        assert result.success is True
        assert result.channel == NotificationChannel.WEBHOOK

    def test_protocol_conformance(self) -> None:
        assert isinstance(InMemorySlackNotifier(), ChannelNotifier)
        assert isinstance(InMemoryEmailNotifier(), ChannelNotifier)
        assert isinstance(InMemoryWebPushNotifier(), ChannelNotifier)
        assert isinstance(InMemoryWebhookNotifier(), ChannelNotifier)


# --- NotificationDispatcher ---


class TestNotificationDispatcher:
    async def test_dispatch_to_registered_handler(self) -> None:
        dispatcher = NotificationDispatcher()
        slack = InMemorySlackNotifier()
        dispatcher.register(NotificationChannel.SLACK, slack)

        result = await dispatcher.dispatch(_msg())
        assert result.success is True
        assert len(slack.sent) == 1

    async def test_dispatch_unregistered_channel(self) -> None:
        dispatcher = NotificationDispatcher()
        result = await dispatcher.dispatch(_msg(channel=NotificationChannel.EMAIL))
        assert result.success is False
        assert "No handler" in (result.error or "")

    async def test_dispatch_many(self) -> None:
        dispatcher = NotificationDispatcher.create_default()
        messages = [
            _msg(channel=NotificationChannel.SLACK),
            _msg(channel=NotificationChannel.EMAIL, recipient="x@y.com"),
            _msg(channel=NotificationChannel.WEBHOOK, recipient="https://hook.example"),
        ]
        results = await dispatcher.dispatch_many(messages)
        assert len(results) == 3
        assert all(r.success for r in results)

    async def test_handler_exception_returns_failure(self) -> None:
        class FailingNotifier:
            async def send(self, message: NotificationMessage) -> DeliveryResult:
                raise RuntimeError("boom")

        dispatcher = NotificationDispatcher()
        dispatcher.register(NotificationChannel.SLACK, FailingNotifier())  # type: ignore[arg-type]
        result = await dispatcher.dispatch(_msg())
        assert result.success is False
        assert result.error == "boom"

    def test_create_default(self) -> None:
        dispatcher = NotificationDispatcher.create_default()
        assert set(dispatcher.registered_channels) == {
            NotificationChannel.SLACK,
            NotificationChannel.EMAIL,
            NotificationChannel.WEB_PUSH,
            NotificationChannel.WEBHOOK,
        }

    def test_get_handler(self) -> None:
        dispatcher = NotificationDispatcher()
        assert dispatcher.get_handler(NotificationChannel.SLACK) is None
        slack = InMemorySlackNotifier()
        dispatcher.register(NotificationChannel.SLACK, slack)
        assert dispatcher.get_handler(NotificationChannel.SLACK) is slack

    def test_handler_kwargs(self) -> None:
        dispatcher = NotificationDispatcher.create_default()
        info = dispatcher.handler_kwargs()
        assert info["slack"] == "InMemorySlackNotifier"
        assert info["email"] == "InMemoryEmailNotifier"
