"""Channel connection management endpoints."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

router = APIRouter()

# Fixed credential ID so we always overwrite the same record
TELEGRAM_CREDENTIAL_ID = "channel:telegram"


class TelegramConnectionRequest(BaseModel):
    bot_token: str
    webhook_secret: str = ""


class ChannelConnectionStatus(BaseModel):
    channel_type: str
    connected: bool
    bot_username: str = ""
    message: str = ""


async def _get_credential_store(request: Request) -> object | None:
    return getattr(request.app.state, "credential_store", None)


async def restore_telegram_from_store(app: object) -> None:
    """Restore the Telegram adapter from the credential store on startup.

    Called from lifespan after stores are wired.
    """
    credential_store = getattr(app.state, "credential_store", None)
    if credential_store is None:
        return

    cred = await credential_store.get(TELEGRAM_CREDENTIAL_ID)
    if cred is None:
        return

    secret = await credential_store.get_secret(TELEGRAM_CREDENTIAL_ID)
    if not secret:
        return

    # secret stores "token||webhook_secret"
    parts = secret.split("||", 1)
    bot_token = parts[0]
    webhook_secret = parts[1] if len(parts) > 1 else ""

    from lintel.telegram.adapter import TelegramChannelAdapter

    adapter = TelegramChannelAdapter(
        bot_token=bot_token,
        webhook_secret=webhook_secret,
    )

    # Verify the token is still valid
    try:
        await adapter.get_me()
    except Exception:
        logger.warning("telegram.restore.invalid_token", credential_id=TELEGRAM_CREDENTIAL_ID)
        return

    app.state.telegram_adapter = adapter

    channel_registry = getattr(app.state, "channel_registry", None)
    if channel_registry is not None:
        from lintel.contracts.channel_type import ChannelType

        channel_registry.register(ChannelType.TELEGRAM, adapter)

    logger.info("telegram.restored_from_store", bot_username=adapter.bot_username)


async def start_telegram_polling(app: object, adapter: object) -> None:
    """Start Telegram long-polling as a background task."""
    import asyncio

    from lintel.telegram.polling import run_polling
    from lintel.telegram.translator import translate_callback_query, translate_message_update
    from lintel.telegram.webhook import _dispatch_inbound_message

    # Cancel existing polling task if any
    await stop_telegram_polling(app)

    class _AppRequestProxy:
        """Minimal stand-in for FastAPI Request."""

        def __init__(self, _app: object) -> None:
            self.app = _app

    proxy = _AppRequestProxy(app)

    async def _process_update(update: dict[str, Any]) -> None:
        cb = translate_callback_query(update)
        if cb is not None:
            from lintel.telegram.keyboards import parse_callback_data

            try:
                action, _req_id = parse_callback_data(cb[0])
            except ValueError:
                return
            cb_id = cb[1].get("id", "")
            if cb_id:
                await adapter.answer_callback_query(cb_id, text=f"Decision: {action}")
            return

        inbound = translate_message_update(update, bot_username=adapter.bot_username)
        if inbound is None:
            return

        logger.info(
            "telegram.poll.message",
            chat_id=inbound.channel_id,
            sender=inbound.sender_id,
            text=inbound.text[:100],
        )
        await _dispatch_inbound_message(proxy, inbound, adapter)

    task = asyncio.create_task(run_polling(adapter, _process_update))
    app.state._telegram_poll_task = task

    bg = getattr(app.state, "_background_tasks", None)
    if bg is not None:
        bg.add(task)
        task.add_done_callback(bg.discard)


async def stop_telegram_polling(app: object) -> None:
    """Cancel the Telegram polling background task if running."""
    task = getattr(app.state, "_telegram_poll_task", None)
    if task is not None and not task.done():
        task.cancel()
    app.state._telegram_poll_task = None


@router.get("/settings/channels")
async def list_channel_connections(request: Request) -> list[dict[str, Any]]:
    """List all channel connections with status."""
    connections: list[dict[str, Any]] = []

    # Check Slack
    connections.append(
        {
            "channel_type": "slack",
            "connected": hasattr(request.app.state, "slack_app"),
            "bot_username": "",
        }
    )

    # Check Telegram
    telegram_adapter = getattr(request.app.state, "telegram_adapter", None)
    connections.append(
        {
            "channel_type": "telegram",
            "connected": telegram_adapter is not None,
            "bot_username": telegram_adapter.bot_username if telegram_adapter else "",
        }
    )

    return connections


@router.post("/settings/channels/telegram", status_code=201)
async def connect_telegram(
    body: TelegramConnectionRequest,
    request: Request,
) -> dict[str, Any]:
    """Save Telegram bot token and set up webhook."""
    from lintel.contracts.channel_type import ChannelType
    from lintel.telegram.adapter import TelegramChannelAdapter

    adapter = TelegramChannelAdapter(
        bot_token=body.bot_token,
        webhook_secret=body.webhook_secret,
    )

    # Verify the token by calling getMe
    try:
        bot_info = await adapter.get_me()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bot token: {exc}",
        ) from exc

    # Persist to credential store
    credential_store = await _get_credential_store(request)
    if credential_store is not None:
        # Store token and webhook_secret together, separated by ||
        combined_secret = f"{body.bot_token}||{body.webhook_secret}"
        await credential_store.store(
            credential_id=TELEGRAM_CREDENTIAL_ID,
            credential_type="telegram_bot_token",
            name="Telegram Bot",
            secret=combined_secret,
        )

    # Store adapter in app state
    request.app.state.telegram_adapter = adapter

    # Register with channel registry if available
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        channel_registry.register(ChannelType.TELEGRAM, adapter)

    bot_username = bot_info.get("username", "")
    logger.info("telegram.connected", bot_username=bot_username)

    # Start polling loop for local dev (no webhook needed)
    await start_telegram_polling(request.app, adapter)

    return {
        "channel_type": "telegram",
        "connected": True,
        "bot_username": bot_username,
    }


@router.get("/settings/channels/telegram/status")
async def telegram_status(request: Request) -> dict[str, Any]:
    """Test Telegram connection by calling getMe."""
    adapter = getattr(request.app.state, "telegram_adapter", None)
    if adapter is None:
        return {
            "channel_type": "telegram",
            "connected": False,
            "message": "Telegram adapter not configured",
        }

    try:
        bot_info = await adapter.get_me()
        return {
            "channel_type": "telegram",
            "connected": True,
            "bot_username": bot_info.get("username", ""),
            "message": "Connection healthy",
        }
    except Exception as exc:
        return {
            "channel_type": "telegram",
            "connected": False,
            "message": f"Connection failed: {exc}",
        }


@router.delete("/settings/channels/telegram", status_code=204)
async def disconnect_telegram(request: Request) -> None:
    """Disconnect Telegram and remove stored credentials."""
    adapter = getattr(request.app.state, "telegram_adapter", None)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Telegram not connected")

    # Stop polling
    await stop_telegram_polling(request.app)

    # Remove from credential store
    credential_store = await _get_credential_store(request)
    if credential_store is not None:
        with contextlib.suppress(KeyError):
            await credential_store.revoke(TELEGRAM_CREDENTIAL_ID)

    # Remove from app state
    del request.app.state.telegram_adapter

    # Deregister from channel registry
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        from lintel.contracts.channel_type import ChannelType

        if channel_registry.is_registered(ChannelType.TELEGRAM):
            pass  # Registry doesn't support unregister, just leave it

    logger.info("telegram.disconnected")
