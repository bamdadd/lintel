"""Bot scope CRUD and access-check endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.bot_scope_api.resolver import BotScopeResolver
from lintel.bot_scope_api.types import AccessDecision, BotScope, ScopeResource

if TYPE_CHECKING:
    from lintel.bot_scope_api.store import InMemoryBotScopeStore
    from lintel.bots_api.store import InMemoryBotStore
    from lintel.multi_slack_bot_api.store import InMemorySlackBotStore

router = APIRouter()

bot_scope_store_provider: StoreProvider[InMemoryBotScopeStore] = StoreProvider()
bot_store_provider: StoreProvider[InMemoryBotStore] = StoreProvider()
slack_bot_store_provider: StoreProvider[InMemorySlackBotStore] = StoreProvider()


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


class ResolveAccessRequest(BaseModel):
    token: str
    project_id: str | None = None
    workflow_id: str | None = None
    agent_id: str | None = None


class ScopeCheckDetail(BaseModel):
    resource_type: ScopeResource
    resource_id: str
    allowed: bool


class ResolveAccessResponse(BaseModel):
    bot_id: str
    allowed: bool
    checks: list[ScopeCheckDetail] = []
    deny_reason: str = ""


def _get_slack_bot_store() -> InMemorySlackBotStore | None:
    try:
        return slack_bot_store_provider.get()
    except RuntimeError:
        return None


def _build_resolver(
    scope_store: InMemoryBotScopeStore,
    b_store: InMemoryBotStore,
    sb_store: InMemorySlackBotStore | None = None,
) -> BotScopeResolver:
    return BotScopeResolver(
        bot_store=b_store,
        scope_store=scope_store,
        slack_bot_store=sb_store,
    )


@router.post("/bot-scopes/resolve")
async def resolve_access(
    body: ResolveAccessRequest,
    scope_store: InMemoryBotScopeStore = Depends(bot_scope_store_provider),  # noqa: B008
    b_store: InMemoryBotStore = Depends(bot_store_provider),  # noqa: B008
) -> ResolveAccessResponse:
    resolver = _build_resolver(scope_store, b_store, _get_slack_bot_store())
    decision = await resolver.resolve_and_check(
        token=body.token,
        project_id=body.project_id,
        workflow_id=body.workflow_id,
        agent_id=body.agent_id,
    )
    return ResolveAccessResponse(
        bot_id=decision.bot_id,
        allowed=decision.allowed,
        checks=[
            ScopeCheckDetail(
                resource_type=c.resource_type,
                resource_id=c.resource_id,
                allowed=c.allowed,
            )
            for c in decision.checks
        ],
        deny_reason=decision.deny_reason,
    )
