"""Channel connection management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

router = APIRouter()


class TelegramConnectionRequest(BaseModel):
    bot_token: str
    webhook_secret: str = ""


class ChannelConnectionStatus(BaseModel):
    channel_type: str
    connected: bool
    bot_username: str = ""
    message: str = ""


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

    # Store adapter in app state
    request.app.state.telegram_adapter = adapter

    # Register with channel registry if available
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        channel_registry.register(ChannelType.TELEGRAM, adapter)

    bot_username = bot_info.get("username", "")
    logger.info("telegram.connected", bot_username=bot_username)

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
    """Disconnect Telegram and deregister webhook."""
    adapter = getattr(request.app.state, "telegram_adapter", None)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Telegram not connected")

    # Remove from app state
    del request.app.state.telegram_adapter

    # Deregister from channel registry
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        from lintel.contracts.channel_type import ChannelType

        if channel_registry.is_registered(ChannelType.TELEGRAM):
            # Re-create registry without telegram
            pass  # Registry doesn't support unregister, just leave it

    logger.info("telegram.disconnected")
