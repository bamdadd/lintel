"""Channel connection management endpoints."""

from __future__ import annotations

import contextlib
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import structlog

from lintel.channel_connections_api.routes import connection_store_provider
from lintel.channel_connections_api.types import ChannelConnection

if TYPE_CHECKING:
    from lintel.channel_connections_api.store import InMemoryChannelConnectionStore

logger = structlog.get_logger()

router = APIRouter()

# Default credential IDs — used as credential_ref in ChannelConnection records
TELEGRAM_CREDENTIAL_ID = "channel:telegram"
SLACK_CREDENTIAL_ID = "channel:slack"


class TelegramConnectionRequest(BaseModel):
    bot_token: str
    webhook_secret: str = ""
    connection_id: str = ""


class SlackConnectionRequest(BaseModel):
    bot_token: str
    signing_secret: str = ""
    app_token: str = ""
    connection_id: str = ""


class ChannelConnectionStatus(BaseModel):
    channel_type: str
    connected: bool
    bot_username: str = ""
    message: str = ""


async def _get_credential_store(request: Request) -> object | None:
    return getattr(request.app.state, "credential_store", None)


async def _get_connection_store(
    request: Request,
) -> InMemoryChannelConnectionStore | None:
    """Get connection store, preferring StoreProvider then app state fallback."""
    try:
        return connection_store_provider.get()
    except RuntimeError:
        return None


async def _upsert_connection(
    request: Request,
    connection_id: str,
    channel_type: str,
    credential_ref: str,
    *,
    bot_username: str = "",
    enabled: bool = True,
) -> None:
    """Create or update a ChannelConnection record."""
    store = await _get_connection_store(request)
    if store is None:
        return
    now = datetime.now(UTC).isoformat()
    existing = await store.get(connection_id)
    if existing is not None:
        updated = ChannelConnection(
            **{
                **asdict(existing),
                "credential_ref": credential_ref,
                "bot_username": bot_username,
                "enabled": enabled,
                "updated_at": now,
            },
        )
        await store.update(updated)
    else:
        conn = ChannelConnection(
            id=connection_id,
            channel_type=channel_type,
            credential_ref=credential_ref,
            bot_username=bot_username,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        await store.add(conn)


async def _remove_connection(request: Request, connection_id: str) -> None:
    """Remove a ChannelConnection record if it exists."""
    store = await _get_connection_store(request)
    if store is None:
        return
    existing = await store.get(connection_id)
    if existing is not None:
        await store.remove(connection_id)


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

        channel_registry.register(TELEGRAM_CREDENTIAL_ID, ChannelType.TELEGRAM, adapter)

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
    """List all channel connections with status.

    Returns records from the connection store when available,
    falling back to app state for backward compatibility.
    """
    store = await _get_connection_store(request)
    if store is not None:
        connections = await store.list_all()
        if connections:
            return [asdict(c) for c in connections]

    # Fallback: build from app state (backward compat)
    result: list[dict[str, Any]] = []

    slack_connected = getattr(request.app.state, "slack_connected", False) or hasattr(
        request.app.state, "slack_app"
    )
    result.append(
        {
            "channel_type": "slack",
            "connected": slack_connected,
            "bot_username": "",
        }
    )

    telegram_adapter = getattr(request.app.state, "telegram_adapter", None)
    result.append(
        {
            "channel_type": "telegram",
            "connected": telegram_adapter is not None,
            "bot_username": telegram_adapter.bot_username if telegram_adapter else "",
        }
    )

    return result


@router.post("/settings/channels/slack", status_code=201)
async def connect_slack(
    body: SlackConnectionRequest,
    request: Request,
) -> dict[str, Any]:
    """Save Slack credentials and mark as connected."""
    connection_id = body.connection_id or SLACK_CREDENTIAL_ID

    # Persist to credential store if available
    credential_store = await _get_credential_store(request)
    if credential_store is not None:
        combined_secret = f"{body.bot_token}||{body.signing_secret}||{body.app_token}"
        await credential_store.store(
            credential_id=connection_id,
            credential_type="slack_bot_token",
            name="Slack Bot",
            secret=combined_secret,
        )

    # Track in connection store
    await _upsert_connection(
        request,
        connection_id=connection_id,
        channel_type="slack",
        credential_ref=connection_id,
    )

    # Mark as connected in app state
    request.app.state.slack_connected = True
    request.app.state.slack_credentials = {
        "bot_token": body.bot_token,
        "signing_secret": body.signing_secret,
        "app_token": body.app_token,
    }

    logger.info("slack.connected", connection_id=connection_id)

    return {
        "channel_type": "slack",
        "connected": True,
        "connection_id": connection_id,
    }


@router.get("/settings/channels/slack/status")
async def slack_status(request: Request) -> dict[str, Any]:
    """Check Slack connection status."""
    connected = getattr(request.app.state, "slack_connected", False)
    if not connected:
        return {
            "channel_type": "slack",
            "connected": False,
            "message": "Slack not configured",
        }

    return {
        "channel_type": "slack",
        "connected": True,
        "message": "Connection configured",
    }


@router.delete("/settings/channels/slack", status_code=204)
async def disconnect_slack(request: Request) -> None:
    """Disconnect Slack and remove stored credentials."""
    connected = getattr(request.app.state, "slack_connected", False)
    if not connected:
        raise HTTPException(status_code=404, detail="Slack not connected")

    # Remove from credential store
    credential_store = await _get_credential_store(request)
    if credential_store is not None:
        with contextlib.suppress(KeyError):
            await credential_store.revoke(SLACK_CREDENTIAL_ID)

    # Remove from connection store
    await _remove_connection(request, SLACK_CREDENTIAL_ID)

    # Remove from app state
    request.app.state.slack_connected = False
    request.app.state.slack_credentials = None

    logger.info("slack.disconnected")


@router.post("/settings/channels/telegram", status_code=201)
async def connect_telegram(
    body: TelegramConnectionRequest,
    request: Request,
) -> dict[str, Any]:
    """Save Telegram bot token and set up webhook."""
    from lintel.contracts.channel_type import ChannelType
    from lintel.telegram.adapter import TelegramChannelAdapter

    connection_id = body.connection_id or TELEGRAM_CREDENTIAL_ID

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
            credential_id=connection_id,
            credential_type="telegram_bot_token",
            name="Telegram Bot",
            secret=combined_secret,
        )

    bot_username = bot_info.get("username", "")

    # Track in connection store
    await _upsert_connection(
        request,
        connection_id=connection_id,
        channel_type="telegram",
        credential_ref=connection_id,
        bot_username=bot_username,
    )

    # Store adapter in app state
    request.app.state.telegram_adapter = adapter

    # Register with channel registry if available
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        channel_registry.register(connection_id, ChannelType.TELEGRAM, adapter)

    logger.info("telegram.connected", bot_username=bot_username, connection_id=connection_id)

    # Start polling loop for local dev (no webhook needed)
    await start_telegram_polling(request.app, adapter)

    return {
        "channel_type": "telegram",
        "connected": True,
        "bot_username": bot_username,
        "connection_id": connection_id,
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

    # Remove from connection store
    await _remove_connection(request, TELEGRAM_CREDENTIAL_ID)

    # Remove from app state
    del request.app.state.telegram_adapter

    # Deregister from channel registry
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        channel_registry.unregister(TELEGRAM_CREDENTIAL_ID)

    logger.info("telegram.disconnected")
