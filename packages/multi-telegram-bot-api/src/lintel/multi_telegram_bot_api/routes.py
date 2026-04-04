"""Telegram bot CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.multi_telegram_bot_api.store import TelegramBot

if TYPE_CHECKING:
    from lintel.multi_telegram_bot_api.store import InMemoryTelegramBotStore

router = APIRouter()

telegram_bot_store_provider: StoreProvider[InMemoryTelegramBotStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTelegramBotRequest(BaseModel):
    bot_id: str | None = None
    name: str
    bot_token: str
    webhook_secret: str = ""
    channel_bindings: list[str] = Field(default_factory=list)


class UpdateTelegramBotRequest(BaseModel):
    name: str | None = None
    channel_bindings: list[str] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/telegram-bots", status_code=201)
async def create_telegram_bot(
    body: CreateTelegramBotRequest,
    store: InMemoryTelegramBotStore = Depends(telegram_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = TelegramBot(
        name=body.name,
        bot_token=body.bot_token,
        webhook_secret=body.webhook_secret,
        channel_bindings=body.channel_bindings,
        **({"bot_id": body.bot_id} if body.bot_id else {}),
    )
    try:
        await store.add(bot)
    except KeyError:
        raise HTTPException(status_code=409, detail="Telegram bot already exists")  # noqa: B904
    return asdict(bot)


@router.get("/telegram-bots")
async def list_telegram_bots(
    store: InMemoryTelegramBotStore = Depends(telegram_bot_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    bots = await store.list_all()
    return [asdict(b) for b in bots]


@router.get("/telegram-bots/{bot_id}")
async def get_telegram_bot(
    bot_id: str,
    store: InMemoryTelegramBotStore = Depends(telegram_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Telegram bot not found")
    return asdict(bot)


@router.patch("/telegram-bots/{bot_id}")
async def update_telegram_bot(
    bot_id: str,
    body: UpdateTelegramBotRequest,
    store: InMemoryTelegramBotStore = Depends(telegram_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    updated = await store.update(bot_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Telegram bot not found")
    return asdict(updated)


@router.delete("/telegram-bots/{bot_id}", status_code=204)
async def delete_telegram_bot(
    bot_id: str,
    store: InMemoryTelegramBotStore = Depends(telegram_bot_store_provider),  # noqa: B008
) -> None:
    removed = await store.remove(bot_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Telegram bot not found")
