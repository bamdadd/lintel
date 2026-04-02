"""Tests for sandbox subscription and usage tracking domain model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lintel.domain.sandbox.types import (
    SandboxSubscription,
    SandboxUsage,
    SubscriptionTier,
    UsageTracker,
    default_quota,
)

# --- SubscriptionTier ---


class TestSubscriptionTier:
    def test_values(self) -> None:
        assert set(SubscriptionTier) == {
            SubscriptionTier.FREE,
            SubscriptionTier.PRO,
            SubscriptionTier.TEAM,
            SubscriptionTier.ENTERPRISE,
        }

    def test_str_values(self) -> None:
        assert SubscriptionTier.FREE == "free"
        assert SubscriptionTier.ENTERPRISE == "enterprise"


# --- default_quota ---


class TestDefaultQuota:
    def test_free_quota(self) -> None:
        assert default_quota(SubscriptionTier.FREE) == 10_000

    def test_pro_quota(self) -> None:
        assert default_quota(SubscriptionTier.PRO) == 100_000

    def test_team_quota(self) -> None:
        assert default_quota(SubscriptionTier.TEAM) == 500_000

    def test_enterprise_quota(self) -> None:
        assert default_quota(SubscriptionTier.ENTERPRISE) == 5_000_000


# --- SandboxSubscription ---


class TestSandboxSubscription:
    def test_frozen(self) -> None:
        sub = SandboxSubscription(
            sandbox_id="sb-1",
            tier=SubscriptionTier.PRO,
            token_quota=100_000,
        )
        with pytest.raises(AttributeError):
            sub.tokens_used = 999  # type: ignore[misc]

    def test_defaults(self) -> None:
        sub = SandboxSubscription(
            sandbox_id="sb-1",
            tier=SubscriptionTier.FREE,
            token_quota=10_000,
        )
        assert sub.tokens_used == 0
        assert sub.expires_at is None

    def test_with_expiry(self) -> None:
        exp = datetime(2026, 12, 31, tzinfo=UTC)
        sub = SandboxSubscription(
            sandbox_id="sb-1",
            tier=SubscriptionTier.TEAM,
            token_quota=500_000,
            expires_at=exp,
        )
        assert sub.expires_at == exp


# --- SandboxUsage ---


class TestSandboxUsage:
    def test_frozen(self) -> None:
        usage = SandboxUsage(sandbox_id="sb-1", tokens_used=50, quota=100, percentage_used=50.0)
        with pytest.raises(AttributeError):
            usage.tokens_used = 0  # type: ignore[misc]


# --- UsageTracker ---


class TestUsageTracker:
    def _make_tracker(self) -> UsageTracker:
        tracker = UsageTracker()
        tracker.register(
            SandboxSubscription(
                sandbox_id="sb-1",
                tier=SubscriptionTier.FREE,
                token_quota=1000,
            )
        )
        return tracker

    def test_record_usage_returns_remaining(self) -> None:
        tracker = self._make_tracker()
        remaining = tracker.record_usage("sb-1", 300)
        assert remaining == 700

    def test_record_usage_accumulates(self) -> None:
        tracker = self._make_tracker()
        tracker.record_usage("sb-1", 300)
        tracker.record_usage("sb-1", 200)
        usage = tracker.get_usage("sb-1")
        assert usage.tokens_used == 500

    def test_record_usage_clamps_remaining_at_zero(self) -> None:
        tracker = self._make_tracker()
        remaining = tracker.record_usage("sb-1", 1500)
        assert remaining == 0

    def test_record_usage_negative_raises(self) -> None:
        tracker = self._make_tracker()
        with pytest.raises(ValueError, match="non-negative"):
            tracker.record_usage("sb-1", -1)

    def test_record_usage_unknown_sandbox_raises(self) -> None:
        tracker = UsageTracker()
        with pytest.raises(KeyError):
            tracker.record_usage("missing", 100)

    def test_get_usage(self) -> None:
        tracker = self._make_tracker()
        tracker.record_usage("sb-1", 250)
        usage = tracker.get_usage("sb-1")
        assert usage.sandbox_id == "sb-1"
        assert usage.tokens_used == 250
        assert usage.quota == 1000
        assert usage.percentage_used == 25.0

    def test_get_usage_unknown_raises(self) -> None:
        tracker = UsageTracker()
        with pytest.raises(KeyError):
            tracker.get_usage("missing")

    def test_is_within_quota_true(self) -> None:
        tracker = self._make_tracker()
        assert tracker.is_within_quota("sb-1") is True

    def test_is_within_quota_false_when_exceeded(self) -> None:
        tracker = self._make_tracker()
        tracker.record_usage("sb-1", 1001)
        assert tracker.is_within_quota("sb-1") is False

    def test_is_within_quota_false_at_exact_limit(self) -> None:
        tracker = self._make_tracker()
        tracker.record_usage("sb-1", 1000)
        assert tracker.is_within_quota("sb-1") is False

    def test_is_within_quota_unknown_raises(self) -> None:
        tracker = UsageTracker()
        with pytest.raises(KeyError):
            tracker.is_within_quota("missing")

    def test_register_replaces_subscription(self) -> None:
        tracker = self._make_tracker()
        tracker.record_usage("sb-1", 500)
        # Upgrade tier — resets usage since we pass a fresh subscription
        tracker.register(
            SandboxSubscription(
                sandbox_id="sb-1",
                tier=SubscriptionTier.PRO,
                token_quota=100_000,
            )
        )
        usage = tracker.get_usage("sb-1")
        assert usage.tokens_used == 0
        assert usage.quota == 100_000

    def test_subscriptions_property_is_copy(self) -> None:
        tracker = self._make_tracker()
        subs = tracker.subscriptions
        subs.pop("sb-1")
        # Original tracker unaffected
        assert "sb-1" in tracker.subscriptions

    def test_percentage_zero_quota(self) -> None:
        tracker = UsageTracker()
        tracker.register(
            SandboxSubscription(
                sandbox_id="sb-0",
                tier=SubscriptionTier.FREE,
                token_quota=0,
            )
        )
        usage = tracker.get_usage("sb-0")
        assert usage.percentage_used == 0.0
