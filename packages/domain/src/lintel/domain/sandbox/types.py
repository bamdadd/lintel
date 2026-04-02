"""Domain types for Claude Code sandbox subscriptions and usage tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class SubscriptionTier(StrEnum):
    """Subscription tier for Claude Code sandbox access."""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


_DEFAULT_QUOTAS: dict[SubscriptionTier, int] = {
    SubscriptionTier.FREE: 10_000,
    SubscriptionTier.PRO: 100_000,
    SubscriptionTier.TEAM: 500_000,
    SubscriptionTier.ENTERPRISE: 5_000_000,
}


def default_quota(tier: SubscriptionTier) -> int:
    """Return the default token quota for a given tier."""
    return _DEFAULT_QUOTAS[tier]


@dataclass(frozen=True)
class SandboxSubscription:
    """Tracks a Claude Code subscription attached to a sandbox."""

    sandbox_id: str
    tier: SubscriptionTier
    token_quota: int
    tokens_used: int = 0
    expires_at: datetime | None = None


@dataclass(frozen=True)
class SandboxUsage:
    """Point-in-time usage snapshot for a sandbox."""

    sandbox_id: str
    tokens_used: int
    quota: int
    percentage_used: float


class UsageTracker:
    """Tracks token usage per sandbox against subscription quotas."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, SandboxSubscription] = {}

    def register(self, subscription: SandboxSubscription) -> None:
        """Register or replace a subscription for a sandbox."""
        self._subscriptions[subscription.sandbox_id] = subscription

    def record_usage(self, sandbox_id: str, tokens: int) -> int:
        """Record token usage and return remaining tokens.

        Raises ``KeyError`` if the sandbox has no subscription.
        Raises ``ValueError`` if *tokens* is negative.
        """
        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        sub = self._subscriptions[sandbox_id]
        new_used = sub.tokens_used + tokens
        self._subscriptions[sandbox_id] = SandboxSubscription(
            sandbox_id=sub.sandbox_id,
            tier=sub.tier,
            token_quota=sub.token_quota,
            tokens_used=new_used,
            expires_at=sub.expires_at,
        )
        return max(sub.token_quota - new_used, 0)

    def get_usage(self, sandbox_id: str) -> SandboxUsage:
        """Return a usage snapshot for *sandbox_id*.

        Raises ``KeyError`` if no subscription is registered.
        """
        sub = self._subscriptions[sandbox_id]
        pct = (sub.tokens_used / sub.token_quota * 100.0) if sub.token_quota > 0 else 0.0
        return SandboxUsage(
            sandbox_id=sandbox_id,
            tokens_used=sub.tokens_used,
            quota=sub.token_quota,
            percentage_used=round(pct, 2),
        )

    def is_within_quota(self, sandbox_id: str) -> bool:
        """Return ``True`` if the sandbox has not exceeded its token quota.

        Raises ``KeyError`` if no subscription is registered.
        """
        sub = self._subscriptions[sandbox_id]
        return sub.tokens_used < sub.token_quota

    @property
    def subscriptions(self) -> dict[str, SandboxSubscription]:
        """Read-only access to tracked subscriptions."""
        return dict(self._subscriptions)
