"""Bot CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.bots_api.store import InMemoryBotStore
from lintel.domain.events import BotCreated, BotRemoved, BotUpdated
from lintel.domain.types import Bot, BotPlatform, BotStatus

router = APIRouter()

bot_store_provider: StoreProvider[InMemoryBotStore] = StoreProvider()


class CreateBotRequest(BaseModel):
    bot_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    platform: BotPlatform = BotPlatform.CUSTOM
    scopes: list[str] = []
    status: BotStatus = BotStatus.ACTIVE


class UpdateBotRequest(BaseModel):
    name: str | None = None
    platform: BotPlatform | None = None
    scopes: list[str] | None = None
    status: BotStatus | None = None


def _bot_to_dict(bot: Bot) -> dict[str, Any]:
    data = asdict(bot)
    data["scopes"] = list(bot.scopes)
    return data


@router.post("/bots", status_code=201)
async def create_bot(
    body: CreateBotRequest,
    request: Request,
    store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.bot_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bot already exists")
    bot = Bot(
        bot_id=body.bot_id,
        name=body.name,
        platform=body.platform,
        scopes=tuple(body.scopes),
        status=body.status,
    )
    await store.add(bot)
    await dispatch_event(
        request,
        BotCreated(payload={"resource_id": body.bot_id, "name": body.name}),
        stream_id=f"bot:{body.bot_id}",
    )
    return _bot_to_dict(bot)


@router.get("/bots")
async def list_bots(
    store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    bots = await store.list_all()
    return [_bot_to_dict(b) for b in bots]


@router.get("/bots/{bot_id}")
async def get_bot(
    bot_id: str,
    store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return _bot_to_dict(bot)


@router.patch("/bots/{bot_id}")
async def update_bot(
    bot_id: str,
    body: UpdateBotRequest,
    request: Request,
    store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    updates = body.model_dump(exclude_none=True)
    if "scopes" in updates:
        updates["scopes"] = tuple(updates["scopes"])
    updated = Bot(**{**asdict(bot), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        BotUpdated(payload={"resource_id": bot_id, "fields": list(updates.keys())}),
        stream_id=f"bot:{bot_id}",
    )
    return _bot_to_dict(updated)


@router.delete("/bots/{bot_id}", status_code=204)
async def delete_bot(
    bot_id: str,
    request: Request,
    store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> None:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    await store.remove(bot_id)
    await dispatch_event(
        request,
        BotRemoved(payload={"resource_id": bot_id, "name": bot.name}),
        stream_id=f"bot:{bot_id}",
    )
