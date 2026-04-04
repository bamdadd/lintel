"""Tests for BotScopeResolver service."""

from __future__ import annotations

import pytest

from lintel.bot_scope_api.resolver import BotScopeResolver
from lintel.bot_scope_api.store import InMemoryBotScopeStore
from lintel.bot_scope_api.types import BotScope, ScopeResource
from lintel.bots_api.store import InMemoryBotStore
from lintel.domain.types import Bot


@pytest.fixture()
def bot_store() -> InMemoryBotStore:
    return InMemoryBotStore()


@pytest.fixture()
def scope_store() -> InMemoryBotScopeStore:
    return InMemoryBotScopeStore()


@pytest.fixture()
def resolver(
    bot_store: InMemoryBotStore,
    scope_store: InMemoryBotScopeStore,
) -> BotScopeResolver:
    return BotScopeResolver(bot_store=bot_store, scope_store=scope_store)


async def _add_bot(store: InMemoryBotStore, bot_id: str = "bot-1") -> Bot:
    bot = Bot(bot_id=bot_id, name=f"Bot {bot_id}")
    await store.add(bot)
    return bot


async def _add_scope(
    store: InMemoryBotScopeStore,
    bot_id: str,
    resource_type: ScopeResource,
    resource_id: str,
) -> None:
    await store.add(BotScope(bot_id=bot_id, resource_type=resource_type, resource_id=resource_id))


class TestResolveBotByToken:
    async def test_finds_bot_by_token(
        self, resolver: BotScopeResolver, bot_store: InMemoryBotStore
    ) -> None:
        await _add_bot(bot_store, "bot-1")
        assert await resolver.resolve_bot_by_token("bot-1") == "bot-1"

    async def test_returns_none_for_unknown_token(self, resolver: BotScopeResolver) -> None:
        assert await resolver.resolve_bot_by_token("unknown") is None


class TestCheckAccess:
    async def test_allowed_when_scope_matches(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "proj-1")
        decision = await resolver.check_access("bot-1", project_id="proj-1")
        assert decision.allowed is True
        assert len(decision.checks) == 1
        assert decision.checks[0].allowed is True

    async def test_denied_when_scope_missing(
        self,
        resolver: BotScopeResolver,
    ) -> None:
        decision = await resolver.check_access("bot-1", project_id="proj-1")
        assert decision.allowed is False
        assert "proj-1" in decision.deny_reason

    async def test_wildcard_allows_any_resource(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "*")
        decision = await resolver.check_access("bot-1", project_id="any-project")
        assert decision.allowed is True

    async def test_multi_dimension_all_allowed(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "proj-1")
        await _add_scope(scope_store, "bot-1", ScopeResource.WORKFLOW, "wf-1")
        await _add_scope(scope_store, "bot-1", ScopeResource.AGENT, "agent-1")
        decision = await resolver.check_access(
            "bot-1", project_id="proj-1", workflow_id="wf-1", agent_id="agent-1"
        )
        assert decision.allowed is True
        assert len(decision.checks) == 3

    async def test_multi_dimension_partial_denied(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "proj-1")
        # No workflow scope
        decision = await resolver.check_access("bot-1", project_id="proj-1", workflow_id="wf-1")
        assert decision.allowed is False
        assert "workflow:wf-1" in decision.deny_reason

    async def test_no_dimensions_means_allowed(self, resolver: BotScopeResolver) -> None:
        decision = await resolver.check_access("bot-1")
        assert decision.allowed is True
        assert len(decision.checks) == 0

    async def test_wildcard_mixed_with_specific(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "*")
        await _add_scope(scope_store, "bot-1", ScopeResource.WORKFLOW, "wf-1")
        decision = await resolver.check_access("bot-1", project_id="anything", workflow_id="wf-1")
        assert decision.allowed is True


class TestResolveAndCheck:
    async def test_full_flow_allowed(
        self,
        resolver: BotScopeResolver,
        bot_store: InMemoryBotStore,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await _add_bot(bot_store, "bot-1")
        await _add_scope(scope_store, "bot-1", ScopeResource.PROJECT, "proj-1")
        decision = await resolver.resolve_and_check("bot-1", project_id="proj-1")
        assert decision.allowed is True
        assert decision.bot_id == "bot-1"

    async def test_unknown_token_denied(self, resolver: BotScopeResolver) -> None:
        decision = await resolver.resolve_and_check("unknown-token", project_id="proj-1")
        assert decision.allowed is False
        assert decision.bot_id == ""
        assert "Unknown bot token" in decision.deny_reason

    async def test_full_flow_denied_scope(
        self,
        resolver: BotScopeResolver,
        bot_store: InMemoryBotStore,
    ) -> None:
        await _add_bot(bot_store, "bot-1")
        decision = await resolver.resolve_and_check("bot-1", project_id="proj-1")
        assert decision.allowed is False
        assert decision.bot_id == "bot-1"
