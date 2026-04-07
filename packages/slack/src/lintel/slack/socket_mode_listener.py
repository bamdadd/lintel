"""Slack Socket Mode listener — receives inbound events via WebSocket.

Uses slack-bolt's AsyncApp and AsyncSocketModeHandler to listen for:
- Message events → translated to ProcessIncomingMessage commands
- Interactive actions (approval buttons) → translated to GrantApproval/RejectApproval
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp

logger = structlog.get_logger()


class SlackSocketModeListener:
    """Manages a Slack Socket Mode connection.

    Registers message and action handlers on a slack-bolt AsyncApp, then
    connects via AsyncSocketModeHandler using the xapp- app-level token.
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        signing_secret: str = "",
        on_message: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
        on_action: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._signing_secret = signing_secret
        self._on_message = on_message
        self._on_action = on_action
        self._handler: AsyncSocketModeHandler | None = None
        self._app: AsyncApp | None = None
        self._task: asyncio.Task[None] | None = None

    def _build_app(self) -> AsyncApp:
        """Create and configure a slack-bolt AsyncApp with event handlers."""
        from slack_bolt.async_app import AsyncApp

        app = AsyncApp(
            token=self._bot_token,
            signing_secret=self._signing_secret or "not-used-in-socket-mode",
        )

        on_message = self._on_message
        on_action = self._on_action

        @app.event("message")
        async def handle_message(event: dict[str, Any], say: Any) -> None:  # noqa: ANN401
            if on_message is not None:
                await on_message(event)

        if on_action is not None:
            _on_action = on_action

            @app.action({"action_id": "approve:.*"})
            async def handle_approve(ack: Any, body: dict[str, Any]) -> None:  # noqa: ANN401
                await ack()
                await _on_action(body)

            @app.action({"action_id": "reject:.*"})
            async def handle_reject(ack: Any, body: dict[str, Any]) -> None:  # noqa: ANN401
                await ack()
                await _on_action(body)

        return app

    async def start(self) -> None:
        """Start the Socket Mode connection in the background."""
        if self._handler is not None:
            logger.warning("slack.socket_mode.already_running")
            return

        if not self._app_token:
            logger.warning("slack.socket_mode.no_app_token")
            return

        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._app = self._build_app()
        self._handler = AsyncSocketModeHandler(app=self._app, app_token=self._app_token)

        async def _run() -> None:
            try:
                await self._handler.start_async()  # type: ignore[union-attr]
            except asyncio.CancelledError:
                logger.info("slack.socket_mode.cancelled")
            except Exception:
                logger.exception("slack.socket_mode.error")

        self._task = asyncio.create_task(_run())
        logger.info("slack.socket_mode.started")

    async def stop(self) -> None:
        """Stop the Socket Mode connection."""
        if self._handler is not None:
            try:
                await self._handler.close_async()  # type: ignore[no-untyped-call]
            except Exception:
                logger.exception("slack.socket_mode.close_error")
            self._handler = None

        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._app = None
        logger.info("slack.socket_mode.stopped")

    @property
    def is_running(self) -> bool:
        return self._handler is not None and self._task is not None and not self._task.done()
