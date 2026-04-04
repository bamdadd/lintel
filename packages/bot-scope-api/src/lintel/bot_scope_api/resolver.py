"""BotScopeResolver — authorization gate for multi-bot inbound messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lintel.bot_scope_api.types import (
    ScopeDecision,
    ScopeResource,
)

if TYPE_CHECKING:
    from lintel.bot_scope_api.store import InMemoryBotScopeStore

logger = structlog.get_logger()


class BotScopeResolver:
    """Resolves bot identity from a connection and enforces scope."""

    def __init__(
        self,
        scope_store: InMemoryBotScopeStore,
        connection_bot_map: dict[str, str] | None = None,
    ) -> None:
        self._scope_store = scope_store
        self._connection_bot_map: dict[str, str] = connection_bot_map or {}

    def register_connection(self, connection_id: str, bot_id: str) -> None:
        """Map a channel connection to the bot that owns it."""
        self._connection_bot_map[connection_id] = bot_id

    def unregister_connection(self, connection_id: str) -> None:
        """Remove a connection-to-bot mapping."""
        self._connection_bot_map.pop(connection_id, None)

    def resolve_bot_id(self, connection_id: str) -> str | None:
        """Resolve a connection_id to its owning bot_id."""
        return self._connection_bot_map.get(connection_id)

    async def check_access(
        self,
        bot_id: str,
        project_id: str = "",
        workflow_id: str = "",
        agent_id: str = "",
    ) -> ScopeDecision:
        """Check whether a bot has access to the requested resources.

        Empty resource IDs are skipped (no check needed).
        If the bot has no scopes at all, access is denied for any non-empty resource.
        """
        denied: list[tuple[ScopeResource, str]] = []
        checks: list[tuple[ScopeResource, str]] = []

        if project_id:
            checks.append((ScopeResource.PROJECT, project_id))
        if workflow_id:
            checks.append((ScopeResource.WORKFLOW, workflow_id))
        if agent_id:
            checks.append((ScopeResource.AGENT, agent_id))

        if not checks:
            return ScopeDecision(allowed=True, bot_id=bot_id)

        for resource_type, resource_id in checks:
            allowed = await self._scope_store.check(
                bot_id=bot_id,
                resource_type=resource_type.value,
                resource_id=resource_id,
            )
            if not allowed:
                denied.append((resource_type, resource_id))

        if denied:
            logger.info(
                "bot_scope_denied",
                bot_id=bot_id,
                denied=[f"{r.value}:{rid}" for r, rid in denied],
            )
            return ScopeDecision(
                allowed=False,
                bot_id=bot_id,
                denied_resources=tuple(denied),
            )

        logger.debug(
            "bot_scope_allowed",
            bot_id=bot_id,
            checks=[f"{r.value}:{rid}" for r, rid in checks],
        )
        return ScopeDecision(allowed=True, bot_id=bot_id)

    async def check_connection_access(
        self,
        connection_id: str,
        project_id: str = "",
        workflow_id: str = "",
        agent_id: str = "",
    ) -> ScopeDecision:
        """Resolve bot from connection and check access in one call.

        If the connection has no mapped bot, access is allowed (no bot
        scope enforcement applies to unmapped connections).
        """
        bot_id = self.resolve_bot_id(connection_id)
        if bot_id is None:
            return ScopeDecision(allowed=True, bot_id="")

        return await self.check_access(
            bot_id=bot_id,
            project_id=project_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )
