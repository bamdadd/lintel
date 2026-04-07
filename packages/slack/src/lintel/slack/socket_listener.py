"""Slack Socket Mode listener — receives inbound events via WebSocket.

Uses slack-bolt's AsyncSocketModeHandler to connect to Slack's Socket Mode
(requires an xapp- app-level token). Translates incoming events to Lintel
commands and routes them through the chat pipeline.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import structlog

logger = structlog.get_logger()


class SlackSocketListener:
    """Manages a Slack Socket Mode connection.

    Handles message events, interactive actions (approvals), and slash commands.
    Routes inbound messages through the ChatService pipeline, mirroring how the
    Telegram polling adapter works.
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        app_state: Any,  # noqa: ANN401
        *,
        signing_secret: str = "",
        connection_id: str = "",
    ) -> None:
        if not app_token or not app_token.startswith("xapp-"):
            msg = "Slack Socket Mode requires an app-level token (xapp-...)"
            raise ValueError(msg)

        self._bot_token = bot_token
        self._app_token = app_token
        self._signing_secret = signing_secret
        self._connection_id = connection_id
        self._app_state = app_state
        self._task: asyncio.Task[None] | None = None
        self._handler: Any = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the Socket Mode handler as a background task."""
        if self.is_running:
            logger.warning("slack.socket.already_running")
            return

        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from slack_bolt.async_app import AsyncApp

        bolt_app = AsyncApp(
            token=self._bot_token,
            signing_secret=self._signing_secret or "not-used-in-socket-mode",
        )

        self._register_handlers(bolt_app)

        self._handler = AsyncSocketModeHandler(bolt_app, self._app_token)

        self._task = asyncio.create_task(self._run())
        bg = getattr(self._app_state, "_background_tasks", None)
        if bg is not None:
            bg.add(self._task)
            self._task.add_done_callback(bg.discard)

        logger.info("slack.socket.started")

    async def _run(self) -> None:
        """Run the socket mode handler, reconnecting on transient failures."""
        try:
            await self._handler.start_async()
        except asyncio.CancelledError:
            logger.info("slack.socket.cancelled")
        except Exception:
            logger.exception("slack.socket.unexpected_error")

    async def stop(self) -> None:
        """Stop the Socket Mode handler gracefully."""
        if self._handler is not None:
            try:
                await self._handler.close_async()
            except Exception:
                logger.warning("slack.socket.close_error", exc_info=True)
            self._handler = None

        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        self._task = None
        logger.info("slack.socket.stopped")

    def _register_handlers(self, bolt_app: Any) -> None:  # noqa: ANN401
        """Register Slack event handlers on the Bolt app."""

        @bolt_app.event("message")
        async def handle_message(event: dict[str, Any], say: Any) -> None:  # noqa: ANN401
            await self._on_message(event)

        @bolt_app.action({"action_id": "approve:.*"})
        async def handle_approve(ack: Any, body: dict[str, Any]) -> None:  # noqa: ANN401
            await ack()
            await self._on_interactive_action(body)

        @bolt_app.action({"action_id": "reject:.*"})
        async def handle_reject(ack: Any, body: dict[str, Any]) -> None:  # noqa: ANN401
            await ack()
            await self._on_interactive_action(body)

    async def _on_message(self, event: dict[str, Any]) -> None:
        """Handle an inbound Slack message event."""
        from lintel.slack.event_translator import translate_message_event

        cmd = translate_message_event(event, connection_id=self._connection_id)
        if cmd is None:
            logger.debug(
                "slack.socket.message_skipped",
                has_bot_id=bool(event.get("bot_id")),
                subtype=event.get("subtype", ""),
                has_team=bool(event.get("team")),
                has_channel=bool(event.get("channel")),
                event_keys=list(event.keys()),
            )
            return

        logger.info(
            "slack.socket.message",
            channel=event.get("channel", ""),
            user=event.get("user", ""),
            text=(cmd.raw_text[:100] if cmd.raw_text else ""),
        )

        await self._dispatch_to_chat(cmd)

    async def _on_interactive_action(self, body: dict[str, Any]) -> None:
        """Handle an interactive action (approval/reject buttons)."""
        from lintel.slack.event_translator import translate_approval_action

        approval_cmd = translate_approval_action(body)
        if approval_cmd is None:
            logger.warning("slack.socket.unknown_action", body_keys=list(body.keys()))
            return

        logger.info(
            "slack.socket.approval_action",
            action_type=type(approval_cmd).__name__,
        )

        # Dispatch approval through the event bus
        event_bus = getattr(self._app_state, "event_bus", None)
        if event_bus is not None:
            from lintel.contracts.events import EventEnvelope

            event = EventEnvelope(
                event_type=type(approval_cmd).__name__,
                payload={
                    "thread_ref": str(approval_cmd.thread_ref),
                    "gate_type": approval_cmd.gate_type,
                },
            )
            await event_bus.publish(event)

    async def _dispatch_to_chat(self, cmd: Any) -> None:  # noqa: ANN401
        """Route an inbound message through the ChatService pipeline."""
        from uuid import uuid4

        chat_store = getattr(self._app_state, "chat_store", None)
        chat_router = getattr(self._app_state, "chat_router", None)
        if chat_store is None or chat_router is None:
            logger.warning(
                "slack.socket.missing_deps",
                has_store=chat_store is not None,
                has_router=chat_router is not None,
            )
            return

        # Build a stable conversation key from workspace + channel + thread
        conv_key = (
            f"slack:{cmd.thread_ref.workspace_id}"
            f":{cmd.thread_ref.channel_id}"
            f":{cmd.thread_ref.thread_ts}"
        )

        # Find existing conversation or create new one
        all_convs = await chat_store.list_all()
        conv = None
        for c in all_convs:
            if c.get("external_thread_id") == conv_key:
                conv = c
                break

        if conv is None:
            conversation_id = uuid4().hex
            conv = await chat_store.create(
                conversation_id=conversation_id,
                user_id=cmd.sender_id,
                display_name=f"Slack:{cmd.sender_id}",
                project_id=None,
            )
            await chat_store.update_fields(
                conversation_id,
                external_thread_id=conv_key,
                source="slack",
            )
        else:
            conversation_id = conv["conversation_id"]

        # Store the user message
        await chat_store.add_message(
            conversation_id,
            user_id=cmd.sender_id,
            display_name=f"Slack:{cmd.sender_id}",
            role="user",
            content=cmd.raw_text,
        )

        # Classify and handle through ChatService
        from lintel.chat_api.service import ChatService

        class _AppRequestProxy:
            """Minimal stand-in for FastAPI Request."""

            def __init__(self, _app_state: Any) -> None:  # noqa: ANN401
                self.app = type("_App", (), {"state": _app_state})()

        proxy = _AppRequestProxy(self._app_state)
        svc = ChatService(proxy, chat_store)  # type: ignore[arg-type]
        model_policy, api_base = await svc.resolve_model(None)
        result = await chat_router.classify(
            cmd.raw_text,
            model_policy=model_policy,
            api_base=api_base,
            enabled_workflows=await svc.get_enabled_workflows(),
        )

        reply = await svc.handle_classified_message(
            conversation_id,
            cmd.raw_text,
            result,
            model_policy,
            api_base,
        )

        # Send the reply back to Slack
        if reply:
            from slack_sdk.web.async_client import AsyncWebClient

            from lintel.slack.adapter import SlackChannelAdapter

            client = AsyncWebClient(token=self._bot_token)
            adapter = SlackChannelAdapter(client)
            try:
                await adapter.send_message(cmd.thread_ref, reply)
            except Exception:
                logger.exception(
                    "slack.socket.send_reply_failed",
                    channel=cmd.thread_ref.channel_id,
                )
