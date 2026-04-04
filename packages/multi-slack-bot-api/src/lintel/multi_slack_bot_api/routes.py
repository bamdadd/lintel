"""Slack bot CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.multi_slack_bot_api.store import SlackBot

if TYPE_CHECKING:
    from lintel.multi_slack_bot_api.store import InMemorySlackBotStore

router = APIRouter()

slack_bot_store_provider: StoreProvider[InMemorySlackBotStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateSlackBotRequest(BaseModel):
    bot_id: str | None = None
    name: str
    workspace_id: str
    bot_token: str
    app_id: str = ""
    scopes: list[str] = Field(default_factory=list)
    channel_bindings: list[str] = Field(default_factory=list)


class UpdateSlackBotRequest(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    channel_bindings: list[str] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/slack-bots", status_code=201)
async def create_slack_bot(
    body: CreateSlackBotRequest,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = SlackBot(
        name=body.name,
        workspace_id=body.workspace_id,
        bot_token=body.bot_token,
        app_id=body.app_id,
        scopes=body.scopes,
        channel_bindings=body.channel_bindings,
        **({"bot_id": body.bot_id} if body.bot_id else {}),
    )
    try:
        await store.add(bot)
    except KeyError:
        raise HTTPException(status_code=409, detail="Slack bot already exists")  # noqa: B904
    return asdict(bot)


@router.get("/slack-bots")
async def list_slack_bots(
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    bots = await store.list_all(workspace_id=workspace_id)
    return [asdict(b) for b in bots]


@router.get("/slack-bots/{bot_id}")
async def get_slack_bot(
    bot_id: str,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    bot = await store.get(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Slack bot not found")
    return asdict(bot)


@router.patch("/slack-bots/{bot_id}")
async def update_slack_bot(
    bot_id: str,
    body: UpdateSlackBotRequest,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    updated = await store.update(bot_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Slack bot not found")
    return asdict(updated)


@router.delete("/slack-bots/{bot_id}", status_code=204)
async def delete_slack_bot(
    bot_id: str,
    store: InMemorySlackBotStore = Depends(slack_bot_store_provider),  # noqa: B008
) -> None:
    removed = await store.remove(bot_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Slack bot not found")
