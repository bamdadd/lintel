"""Telegram webhook endpoint — receives and verifies Telegram updates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
import structlog

logger = structlog.get_logger()

router = APIRouter()


@router.post("/channels/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Handle incoming Telegram webhook updates.

    Verifies the X-Telegram-Bot-Api-Secret-Token header against
    the stored secret, then dispatches the update to the appropriate
    handler based on update type (message vs callback_query).
    """
    # Get the adapter from app state
    adapter = getattr(request.app.state, "telegram_adapter", None)
    if adapter is None:
        raise HTTPException(status_code=503, detail="Telegram adapter not configured")

    # Verify webhook secret
    expected_secret = adapter.webhook_secret
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        logger.warning("telegram.webhook.invalid_secret")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Parse the update body
    try:
        update: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON body")  # noqa: B904

    # Handle callback queries (approval responses)
    from lintel.telegram.translator import translate_callback_query

    callback_result = translate_callback_query(update)
    if callback_result is not None:
        callback_data, callback_query = callback_result

        from lintel.telegram.keyboards import parse_callback_data

        try:
            action, approval_request_id = parse_callback_data(callback_data)
        except ValueError:
            logger.warning("telegram.callback.invalid_data", data=callback_data)
            return {"ok": True}

        # Answer the callback query to dismiss loading
        callback_query_id = callback_query.get("id", "")
        if callback_query_id:
            await adapter.answer_callback_query(callback_query_id, text=f"Decision: {action}")

        logger.info(
            "telegram.approval_callback",
            action=action,
            approval_request_id=approval_request_id,
        )
        return {"ok": True}

    # Handle regular messages
    from lintel.telegram.translator import translate_message_update

    bot_username = adapter.bot_username
    inbound = translate_message_update(update, bot_username=bot_username)
    if inbound is None:
        # Update type not handled or filtered out (e.g. non-mentioned group message)
        return {"ok": True}

    # Dispatch to the coordination layer via channel registry if available
    channel_registry = getattr(request.app.state, "channel_registry", None)
    if channel_registry is not None:
        logger.info(
            "telegram.message.received",
            chat_id=inbound.channel_id,
            thread_id=inbound.thread_id,
            sender_id=inbound.sender_id,
        )

    return {"ok": True}
