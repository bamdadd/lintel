"""Telegram webhook endpoint — receives and verifies Telegram updates."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
import structlog

logger = structlog.get_logger()

router = APIRouter()


async def _dispatch_inbound_message(
    request: Request,
    inbound: Any,
    adapter: Any,
) -> None:
    """Create or find a conversation and route the message through ChatService."""
    from lintel.chat_api.service import ChatService

    chat_store = getattr(request.app.state, "chat_store", None)
    chat_router = getattr(request.app.state, "chat_router", None)
    if chat_store is None or chat_router is None:
        logger.warning("telegram.dispatch.missing_deps", has_store=chat_store is not None)
        return

    # Use a stable conversation ID from channel_type + chat_id + thread_id
    conv_key = f"tg:{inbound.channel_id}:{inbound.thread_id}"

    # Look for existing conversation with this key
    all_convs = await chat_store.list_all()
    conv = None
    for c in all_convs:
        if c.get("external_thread_id") == conv_key:
            conv = c
            break

    if conv is None:
        # Create a new conversation
        conversation_id = uuid4().hex
        conv = await chat_store.create(
            conversation_id=conversation_id,
            user_id=inbound.sender_id,
            display_name=f"Telegram:{inbound.sender_id}",
            project_id=None,
        )
        await chat_store.update_fields(
            conversation_id, external_thread_id=conv_key, source="telegram"
        )
    else:
        conversation_id = conv["conversation_id"]

    # Store the user message
    await chat_store.add_message(
        conversation_id,
        user_id=inbound.sender_id,
        display_name=f"Telegram:{inbound.sender_id}",
        role="user",
        content=inbound.text,
    )

    # Classify and handle
    svc = ChatService(request, chat_store)
    model_policy, api_base = await svc.resolve_model(None)
    result = await chat_router.classify(
        inbound.text,
        model_policy=model_policy,
        api_base=api_base,
        enabled_workflows=svc.get_enabled_workflows(),
    )

    reply = await svc.handle_classified_message(
        conversation_id,
        inbound.text,
        result,
        model_policy,
        api_base,
    )

    # Send the reply back to Telegram
    if reply:
        from lintel.contracts.types import ThreadRef

        thread_ref = ThreadRef(
            workspace_id="telegram",
            channel_id=inbound.channel_id,
            thread_ts=inbound.thread_id,
        )
        try:
            await adapter.send_message(thread_ref, reply)
        except Exception:
            logger.exception("telegram.send_reply_failed", chat_id=inbound.channel_id)


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

    logger.info(
        "telegram.message.received",
        chat_id=inbound.channel_id,
        thread_id=inbound.thread_id,
        sender_id=inbound.sender_id,
        text=inbound.text[:100],
    )

    # Dispatch through ChatService
    try:
        await _dispatch_inbound_message(request, inbound, adapter)
    except Exception:
        logger.exception("telegram.dispatch_failed", chat_id=inbound.channel_id)

    return {"ok": True}
