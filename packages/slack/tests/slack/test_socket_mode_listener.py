"""Tests for SlackSocketModeListener."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.slack.socket_mode_listener import SlackSocketModeListener


class TestSlackSocketModeListener:
    def test_init_stores_credentials(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test",
            signing_secret="secret",
        )
        assert listener._bot_token == "xoxb-test"
        assert listener._app_token == "xapp-test"
        assert not listener.is_running

    def test_is_running_false_when_not_started(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test",
        )
        assert not listener.is_running

    async def test_start_without_app_token_is_noop(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="",
        )
        await listener.start()
        assert listener._handler is None
        assert not listener.is_running

    async def test_stop_cancels_task_and_clears_state(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
        )

        mock_handler = MagicMock()
        mock_handler.close_async = AsyncMock()
        listener._handler = mock_handler

        mock_task = MagicMock()
        mock_task.done.return_value = False
        listener._task = mock_task

        await listener.stop()

        mock_handler.close_async.assert_awaited_once()
        mock_task.cancel.assert_called_once()
        assert listener._handler is None
        assert listener._task is None
        assert not listener.is_running

    async def test_stop_when_not_running_is_safe(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
        )
        await listener.stop()

    async def test_start_twice_warns_and_returns(self) -> None:
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
        )
        listener._handler = MagicMock()
        await listener.start()
        assert isinstance(listener._handler, MagicMock)

    def test_build_app_returns_async_app(self) -> None:
        from slack_bolt.async_app import AsyncApp

        on_message = AsyncMock()
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
            on_message=on_message,
        )
        app = listener._build_app()
        assert isinstance(app, AsyncApp)

    def test_build_app_with_action_handler(self) -> None:
        from slack_bolt.async_app import AsyncApp

        on_action = AsyncMock()
        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
            on_action=on_action,
        )
        app = listener._build_app()
        assert isinstance(app, AsyncApp)

    def test_build_app_without_callbacks(self) -> None:
        from slack_bolt.async_app import AsyncApp

        listener = SlackSocketModeListener(
            bot_token="xoxb-test",
            app_token="xapp-test-token",
        )
        app = listener._build_app()
        assert isinstance(app, AsyncApp)


class TestSlackSocketListenerIntegration:
    """Test the high-level SlackSocketListener."""

    def test_socket_listener_requires_xapp_token(self) -> None:
        import pytest

        from lintel.slack.socket_listener import SlackSocketListener

        with pytest.raises(ValueError, match="xapp-"):
            SlackSocketListener(
                bot_token="xoxb-test",
                app_token="bad-token",
                app_state=MagicMock(),
            )

    def test_socket_listener_accepts_valid_token(self) -> None:
        from lintel.slack.socket_listener import SlackSocketListener

        listener = SlackSocketListener(
            bot_token="xoxb-test",
            app_token="xapp-valid-token",
            app_state=MagicMock(),
            connection_id="channel:slack",
        )
        assert not listener.is_running

    async def test_socket_listener_stop_when_not_started(self) -> None:
        from lintel.slack.socket_listener import SlackSocketListener

        listener = SlackSocketListener(
            bot_token="xoxb-test",
            app_token="xapp-valid-token",
            app_state=MagicMock(),
        )
        await listener.stop()
