"""Tests for bot runtime types."""

from lintel.bot_runtime.types import BotConnectionState, BotHealth, _ManagedBot


def test_bot_health_touch_updates_heartbeat() -> None:
    health = BotHealth(bot_id="b1")
    assert health.last_heartbeat == ""
    health.touch()
    assert health.last_heartbeat != ""


def test_bot_health_mark_connected() -> None:
    health = BotHealth(bot_id="b1", reconnect_attempts=3, error="old error")
    health.mark_connected()
    assert health.state == BotConnectionState.CONNECTED
    assert health.error == ""
    assert health.reconnect_attempts == 0
    assert health.started_at != ""


def test_bot_health_mark_failed() -> None:
    health = BotHealth(bot_id="b1")
    health.mark_failed("connection refused")
    assert health.state == BotConnectionState.FAILED
    assert health.error == "connection refused"


def test_bot_health_mark_reconnecting_increments() -> None:
    health = BotHealth(bot_id="b1")
    assert health.reconnect_attempts == 0
    health.mark_reconnecting()
    assert health.state == BotConnectionState.RECONNECTING
    assert health.reconnect_attempts == 1
    health.mark_reconnecting()
    assert health.reconnect_attempts == 2


def test_managed_bot_post_init_sets_health_bot_id() -> None:
    managed = _ManagedBot(bot_id="b1", platform="slack")
    assert managed.health.bot_id == "b1"
