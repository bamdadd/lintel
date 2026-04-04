"""Tests for BotScopeResolver."""

from __future__ import annotations

import pytest

from lintel.bot_scope_api.resolver import BotScopeResolver
from lintel.bot_scope_api.store import InMemoryBotScopeStore
from lintel.bot_scope_api.types import BotScope, ScopeResource


@pytest.fixture()
def scope_store() -> InMemoryBotScopeStore:
    return InMemoryBotScopeStore()


@pytest.fixture()
def resolver(scope_store: InMemoryBotScopeStore) -> BotScopeResolver:
    return BotScopeResolver(scope_store=scope_store)


class TestResolveBot:
    def test_resolve_registered_connection(self, resolver: BotScopeResolver) -> None:
        resolver.register_connection("conn-1", "bot-1")
        assert resolver.resolve_bot_id("conn-1") == "bot-1"

    def test_resolve_unregistered_connection(self, resolver: BotScopeResolver) -> None:
        assert resolver.resolve_bot_id("unknown") is None

    def test_unregister_connection(self, resolver: BotScopeResolver) -> None:
        resolver.register_connection("conn-1", "bot-1")
        resolver.unregister_connection("conn-1")
        assert resolver.resolve_bot_id("conn-1") is None


class TestCheckAccess:
    async def test_no_checks_always_allowed(self, resolver: BotScopeResolver) -> None:
        decision = await resolver.check_access("bot-1")
        assert decision.allowed is True
        assert decision.reason == ""

    async def test_project_allowed(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        decision = await resolver.check_access("bot-1", project_id="proj-1")
        assert decision.allowed is True

    async def test_project_denied(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        decision = await resolver.check_access("bot-1", project_id="proj-99")
        assert decision.allowed is False
        assert len(decision.denied_resources) == 1
        assert decision.denied_resources[0] == (ScopeResource.PROJECT, "proj-99")
        assert "proj-99" in decision.reason

    async def test_wildcard_grants_all(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="*")
        )
        decision = await resolver.check_access("bot-1", project_id="any-project")
        assert decision.allowed is True

    async def test_multi_resource_check(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.WORKFLOW, resource_id="*")
        )
        decision = await resolver.check_access(
            "bot-1", project_id="proj-1", workflow_id="feature_to_pr"
        )
        assert decision.allowed is True

    async def test_multi_resource_partial_denied(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        # No workflow scopes
        decision = await resolver.check_access(
            "bot-1", project_id="proj-1", workflow_id="feature_to_pr"
        )
        assert decision.allowed is False
        assert len(decision.denied_resources) == 1
        assert decision.denied_resources[0] == (ScopeResource.WORKFLOW, "feature_to_pr")

    async def test_all_three_resources_denied(
        self,
        resolver: BotScopeResolver,
    ) -> None:
        # Bot has no scopes at all
        decision = await resolver.check_access(
            "bot-1", project_id="p", workflow_id="w", agent_id="a"
        )
        assert decision.allowed is False
        assert len(decision.denied_resources) == 3


class TestCheckConnectionAccess:
    async def test_unmapped_connection_is_allowed(
        self,
        resolver: BotScopeResolver,
    ) -> None:
        decision = await resolver.check_connection_access("unknown-conn", project_id="proj-1")
        assert decision.allowed is True
        assert decision.bot_id == ""

    async def test_mapped_connection_checks_bot_scopes(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        resolver.register_connection("conn-1", "bot-1")
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        decision = await resolver.check_connection_access("conn-1", project_id="proj-1")
        assert decision.allowed is True
        assert decision.bot_id == "bot-1"

    async def test_mapped_connection_denied(
        self,
        resolver: BotScopeResolver,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        resolver.register_connection("conn-1", "bot-1")
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        decision = await resolver.check_connection_access("conn-1", project_id="proj-other")
        assert decision.allowed is False
        assert decision.bot_id == "bot-1"


class TestWildcardInStore:
    async def test_wildcard_check_via_store(
        self,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        await scope_store.add(
            BotScope(bot_id="bot-w", resource_type=ScopeResource.WORKFLOW, resource_id="*")
        )
        assert await scope_store.check("bot-w", "workflow", "feature_to_pr") is True
        assert await scope_store.check("bot-w", "workflow", "bug_fix") is True
        assert await scope_store.check("bot-w", "project", "anything") is False
