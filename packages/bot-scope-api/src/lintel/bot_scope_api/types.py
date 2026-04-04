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


ALL_RESOURCES = "*"
"""Wildcard resource_id granting access to all resources of a given type."""


@dataclass(frozen=True)
class BotScopeSet:
    """All scopes assigned to a single bot."""

    bot_id: str
    scopes: tuple[BotScope, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopeCheckResult:
    """Outcome of checking a single scope dimension."""

    resource_type: ScopeResource
    resource_id: str
    allowed: bool


@dataclass(frozen=True)
class ScopeDecision:
    """Full access decision across all requested dimensions."""

    bot_id: str
    allowed: bool
    checks: tuple[ScopeCheckResult, ...] = field(default_factory=tuple)
    deny_reason: str = ""
