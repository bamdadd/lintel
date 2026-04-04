"""Bot scope domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScopeResource(StrEnum):
    """Resource types a bot scope can grant access to."""

    PROJECT = "project"
    WORKFLOW = "workflow"
    AGENT = "agent"


class AccessDecision(StrEnum):
    """Result of a scope check."""

    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True)
class BotScope:
    """Grants a bot access to a specific resource."""

    bot_id: str
    resource_type: ScopeResource
    resource_id: str


@dataclass(frozen=True)
class BotScopeSet:
    """All scopes assigned to a single bot."""

    bot_id: str
    scopes: tuple[BotScope, ...] = field(default_factory=tuple)


WILDCARD = "*"
"""Wildcard resource_id — grants access to all resources of a given type."""


@dataclass(frozen=True)
class ScopeCheckRequest:
    """Request to check multiple resource accesses at once."""

    bot_id: str
    project_id: str = ""
    workflow_id: str = ""
    agent_id: str = ""


@dataclass(frozen=True)
class ScopeDecision:
    """Result of a multi-resource scope check."""

    allowed: bool
    bot_id: str
    denied_resources: tuple[tuple[ScopeResource, str], ...] = field(default_factory=tuple)

    @property
    def reason(self) -> str:
        if self.allowed:
            return ""
        parts = [f"{res.value} '{rid}'" for res, rid in self.denied_resources]
        return f"Bot '{self.bot_id}' is not authorized for: {', '.join(parts)}"
