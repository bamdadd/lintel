"""Bot scope CRUD and access-check endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.bot_scope_api.types import AccessDecision, BotScope, ScopeResource

if TYPE_CHECKING:
    from lintel.bot_scope_api.store import InMemoryBotScopeStore

router = APIRouter()

bot_scope_store_provider: StoreProvider[InMemoryBotScopeStore] = StoreProvider()


class CreateBotScopeRequest(BaseModel):
    bot_id: str
    resource_type: ScopeResource
    resource_id: str


class CheckBotScopeRequest(BaseModel):
    bot_id: str
    resource_type: ScopeResource
    resource_id: str


class CheckBotScopeResponse(BaseModel):
    bot_id: str
    resource_type: ScopeResource
    resource_id: str
    decision: AccessDecision


@router.post("/bot-scopes", status_code=201)
async def create_bot_scope(
    body: CreateBotScopeRequest,
    store: InMemoryBotScopeStore = Depends(bot_scope_store_provider),  # noqa: B008
) -> dict[str, Any]:
    scope = BotScope(
        bot_id=body.bot_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
    )
    await store.add(scope)
    return {
        "bot_id": scope.bot_id,
        "resource_type": scope.resource_type.value,
        "resource_id": scope.resource_id,
    }


@router.get("/bot-scopes/{bot_id}")
async def get_bot_scopes(
    bot_id: str,
    store: InMemoryBotScopeStore = Depends(bot_scope_store_provider),  # noqa: B008
) -> dict[str, Any]:
    scope_set = await store.get(bot_id)
    if scope_set is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {
        "bot_id": scope_set.bot_id,
        "scopes": [
            {
                "resource_type": s.resource_type.value,
                "resource_id": s.resource_id,
            }
            for s in scope_set.scopes
        ],
    }


@router.post("/bot-scopes/check")
async def check_bot_scope(
    body: CheckBotScopeRequest,
    store: InMemoryBotScopeStore = Depends(bot_scope_store_provider),  # noqa: B008
) -> CheckBotScopeResponse:
    allowed = await store.check(
        bot_id=body.bot_id,
        resource_type=body.resource_type.value,
        resource_id=body.resource_id,
    )
    return CheckBotScopeResponse(
        bot_id=body.bot_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        decision=AccessDecision.ALLOWED if allowed else AccessDecision.DENIED,
    )
