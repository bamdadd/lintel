"""Tests for bot scope enforcement in ChatService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.bot_scope_api.resolver import BotScopeResolver
from lintel.bot_scope_api.store import InMemoryBotScopeStore
from lintel.bot_scope_api.types import BotScope, ScopeResource
from lintel.chat_api.service import ChatService


def _make_fake_request(
    *,
    bot_scope_resolver: BotScopeResolver | None = None,
    has_dispatcher: bool = True,
) -> MagicMock:
    """Build a minimal mock Request with app.state attributes."""
    request = MagicMock()
    request.app.state.bot_scope_resolver = bot_scope_resolver
    request.app.state.command_dispatcher = AsyncMock() if has_dispatcher else None
    request.app.state.project_store = None
    request.app.state.work_item_store = None
    request.app.state.trigger_store = None
    request.app.state.pipeline_store = None
    request.app.state.audit_entry_store = None
    request.app.state.repository_store = None
    return request


class FakeChatStore:
    """Minimal chat store for testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, object]] = {}
        self._messages: dict[str, list[dict[str, str]]] = {}

    async def get(self, conversation_id: str) -> dict[str, object] | None:
        return self._data.get(conversation_id)

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        display_name: str,
        role: str,
        content: str,
    ) -> None:
        self._messages.setdefault(conversation_id, []).append({"role": role, "content": content})

    async def update_fields(self, conversation_id: str, **fields: object) -> None:
        if conversation_id not in self._data:
            self._data[conversation_id] = {}
        self._data[conversation_id].update(fields)

    def seed(self, conversation_id: str, **fields: object) -> None:
        self._data[conversation_id] = dict(fields)

    def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        return self._messages.get(conversation_id, [])


class TestBotScopeInDispatch:
    async def test_no_resolver_allows_dispatch(self) -> None:
        """When no resolver is wired, dispatch proceeds normally."""
        store = FakeChatStore()
        store.seed("conv-1", connection_id="conn-1")
        request = _make_fake_request(bot_scope_resolver=None)
        service = ChatService(request, store)  # type: ignore[arg-type]

        # dispatch_workflow will fail at project resolution, but the scope
        # check itself should pass
        decision = await service._check_bot_scope("conv-1", project_id="proj-1")
        assert decision.allowed is True

    async def test_unmapped_connection_allows(self) -> None:
        """Connection not mapped to any bot — scope check passes."""
        scope_store = InMemoryBotScopeStore()
        resolver = BotScopeResolver(scope_store=scope_store)
        store = FakeChatStore()
        store.seed("conv-1", connection_id="conn-1")
        request = _make_fake_request(bot_scope_resolver=resolver)
        service = ChatService(request, store)  # type: ignore[arg-type]

        decision = await service._check_bot_scope("conv-1", project_id="proj-1")
        assert decision.allowed is True

    async def test_bot_with_matching_scope_allows(self) -> None:
        scope_store = InMemoryBotScopeStore()
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.WORKFLOW, resource_id="*")
        )
        resolver = BotScopeResolver(scope_store=scope_store)
        resolver.register_connection("conn-1", "bot-1")

        store = FakeChatStore()
        store.seed("conv-1", connection_id="conn-1")
        request = _make_fake_request(bot_scope_resolver=resolver)
        service = ChatService(request, store)  # type: ignore[arg-type]

        decision = await service._check_bot_scope(
            "conv-1", project_id="proj-1", workflow_id="feature_to_pr"
        )
        assert decision.allowed is True

    async def test_bot_denied_posts_message(self) -> None:
        scope_store = InMemoryBotScopeStore()
        await scope_store.add(
            BotScope(bot_id="bot-1", resource_type=ScopeResource.PROJECT, resource_id="proj-1")
        )
        resolver = BotScopeResolver(scope_store=scope_store)
        resolver.register_connection("conn-1", "bot-1")

        store = FakeChatStore()
        store.seed("conv-1", connection_id="conn-1")
        request = _make_fake_request(bot_scope_resolver=resolver)
        service = ChatService(request, store)  # type: ignore[arg-type]

        decision = await service._check_bot_scope("conv-1", project_id="proj-other")
        assert decision.allowed is False
        assert "proj-other" in decision.reason

    async def test_no_connection_id_allows(self) -> None:
        """Conversation without connection_id — no scope check needed."""
        scope_store = InMemoryBotScopeStore()
        resolver = BotScopeResolver(scope_store=scope_store)

        store = FakeChatStore()
        store.seed("conv-1")  # No connection_id
        request = _make_fake_request(bot_scope_resolver=resolver)
        service = ChatService(request, store)  # type: ignore[arg-type]

        decision = await service._check_bot_scope("conv-1", project_id="proj-1")
        assert decision.allowed is True

    async def test_nonexistent_conversation_allows(self) -> None:
        """Non-existent conversation — no scope check needed."""
        scope_store = InMemoryBotScopeStore()
        resolver = BotScopeResolver(scope_store=scope_store)

        store = FakeChatStore()
        request = _make_fake_request(bot_scope_resolver=resolver)
        service = ChatService(request, store)  # type: ignore[arg-type]

        decision = await service._check_bot_scope("nonexistent", project_id="proj-1")
        assert decision.allowed is True
