"""Bot scope resolver — enforces multi-dimensional scope checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.bot_scope_api.types import (
    ScopeCheckResult,
    ScopeDecision,
    ScopeResource,
)

if TYPE_CHECKING:
    from lintel.bot_scope_api.store import InMemoryBotScopeStore
    from lintel.bots_api.store import InMemoryBotStore


class BotScopeResolver:
    """Resolves which bot handled a message and enforces scope."""

    def __init__(
        self,
        bot_store: InMemoryBotStore,
        scope_store: InMemoryBotScopeStore,
    ) -> None:
        self._bot_store = bot_store
        self._scope_store = scope_store

    async def resolve_bot_by_token(self, token: str) -> str | None:
        """Find the bot_id that owns the given token/credential.

        Matches against the bot's ``bot_id`` field since the simple Bot
        dataclass does not carry a separate token.  In a production system
        this would look up a credential store.
        """
        bots = await self._bot_store.list_all()
        for bot in bots:
            if bot.bot_id == token:
                return bot.bot_id
        return None

    async def check_access(
        self,
        bot_id: str,
        *,
        project_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
    ) -> ScopeDecision:
        """Check whether *bot_id* may access the given resources.

        Each non-``None`` dimension is checked against the scope store.
        If **no** dimensions are provided the request is allowed (nothing to deny).
        """
        checks: list[ScopeCheckResult] = []
        dimensions: list[tuple[ScopeResource, str | None]] = [
            (ScopeResource.PROJECT, project_id),
            (ScopeResource.WORKFLOW, workflow_id),
            (ScopeResource.AGENT, agent_id),
        ]

        for resource_type, resource_id in dimensions:
            if resource_id is None:
                continue
            allowed = await self._scope_store.check(
                bot_id=bot_id,
                resource_type=resource_type.value,
                resource_id=resource_id,
            )
            checks.append(
                ScopeCheckResult(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    allowed=allowed,
                )
            )

        denied = [c for c in checks if not c.allowed]
        if denied:
            reasons = [f"{c.resource_type.value}:{c.resource_id}" for c in denied]
            return ScopeDecision(
                bot_id=bot_id,
                allowed=False,
                checks=tuple(checks),
                deny_reason=f"Access denied for: {', '.join(reasons)}",
            )

        return ScopeDecision(
            bot_id=bot_id,
            allowed=True,
            checks=tuple(checks),
        )

    async def resolve_and_check(
        self,
        token: str,
        *,
        project_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
    ) -> ScopeDecision:
        """Resolve bot from token and check access in one call."""
        bot_id = await self.resolve_bot_by_token(token)
        if bot_id is None:
            return ScopeDecision(
                bot_id="",
                allowed=False,
                deny_reason="Unknown bot token",
            )
        return await self.check_access(
            bot_id,
            project_id=project_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )
