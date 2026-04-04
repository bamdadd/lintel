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
