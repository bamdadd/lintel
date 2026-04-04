"""In-memory bot scope store."""

from __future__ import annotations

from lintel.bot_scope_api.types import WILDCARD, BotScope, BotScopeSet


class InMemoryBotScopeStore:
    """Simple in-memory store for bot scopes."""

    def __init__(self) -> None:
        self._scopes: dict[str, list[BotScope]] = {}

    async def add(self, scope: BotScope) -> None:
        self._scopes.setdefault(scope.bot_id, []).append(scope)

    async def get(self, bot_id: str) -> BotScopeSet | None:
        scopes = self._scopes.get(bot_id)
        if scopes is None:
            return None
        return BotScopeSet(bot_id=bot_id, scopes=tuple(scopes))

    async def list_all(self) -> list[BotScopeSet]:
        return [
            BotScopeSet(bot_id=bid, scopes=tuple(scopes)) for bid, scopes in self._scopes.items()
        ]

    async def check(
        self,
        bot_id: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        scopes = self._scopes.get(bot_id, [])
        return any(
            s.resource_type.value == resource_type
            and (s.resource_id == resource_id or s.resource_id == WILDCARD)
            for s in scopes
        )

    async def remove(self, bot_id: str) -> None:
        self._scopes.pop(bot_id, None)
