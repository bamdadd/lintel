"""Feature flags and A/B testing domain model.

Provides deterministic flag evaluation and hash-based variant assignment
for feature rollouts and controlled experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
from typing import Any


class RuleOperator(StrEnum):
    """Comparison operators for targeting rules."""

    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    CONTAINS = "contains"


@dataclass(frozen=True)
class TargetingRule:
    """A single targeting condition evaluated against a context dict."""

    attribute: str
    operator: RuleOperator
    value: Any


@dataclass(frozen=True)
class Variant:
    """A named variant in an A/B test."""

    id: str
    name: str
    config: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureFlag:
    """A feature flag with optional percentage rollout and targeting rules."""

    id: str
    name: str
    enabled: bool = False
    rollout_percentage: float = 100.0
    targeting_rules: list[TargetingRule] = field(default_factory=list)


@dataclass(frozen=True)
class ABTest:
    """An A/B test with weighted variant traffic allocation."""

    id: str
    name: str
    variants: list[Variant] = field(default_factory=list)
    traffic_allocation: dict[str, float] = field(default_factory=dict)


def _hash_key(flag_id: str, context_key: str) -> float:
    """Return a deterministic float in [0, 100) from flag id and context key."""
    digest = hashlib.sha256(f"{flag_id}:{context_key}".encode()).hexdigest()
    return int(digest[:8], 16) % 10000 / 100.0


class FeatureFlagEngine:
    """Evaluates feature flags and assigns A/B test variants."""

    def is_enabled(self, flag: FeatureFlag, context: dict[str, Any]) -> bool:
        """Check whether *flag* is enabled for the given *context*.

        Evaluation order:
        1. ``flag.enabled`` must be True.
        2. All targeting rules must match the context.
        3. Rollout percentage is checked via deterministic hashing on
           ``context["user_id"]`` (or falls back to ``context["id"]``).
        """
        if not flag.enabled:
            return False

        if not self._matches_rules(flag.targeting_rules, context):
            return False

        if flag.rollout_percentage >= 100.0:
            return True
        if flag.rollout_percentage <= 0.0:
            return False

        context_key = str(context.get("user_id", context.get("id", "")))
        return _hash_key(flag.id, context_key) < flag.rollout_percentage

    def get_variant(self, test: ABTest, context: dict[str, Any]) -> Variant:
        """Return the variant assigned to *context* for the given *test*.

        Assignment is deterministic: the same context key always receives the
        same variant.  Traffic allocation weights are normalised and mapped to
        consecutive hash-space buckets.

        Raises ``ValueError`` when the test has no variants.
        """
        if not test.variants:
            msg = f"ABTest '{test.name}' has no variants"
            raise ValueError(msg)

        context_key = str(context.get("user_id", context.get("id", "")))
        h = _hash_key(test.id, context_key)

        total = sum(test.traffic_allocation.get(v.id, 0.0) for v in test.variants)
        if total <= 0:
            # Equal split when no allocation specified.
            idx = int(h * len(test.variants) / 100.0) % len(test.variants)
            return test.variants[idx]

        cumulative = 0.0
        for variant in test.variants:
            weight = test.traffic_allocation.get(variant.id, 0.0)
            cumulative += (weight / total) * 100.0
            if h < cumulative:
                return variant

        # Floating-point edge case — return last variant.
        return test.variants[-1]

    # ------------------------------------------------------------------
    # Targeting rule evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_rules(
        rules: list[TargetingRule],
        context: dict[str, Any],
    ) -> bool:
        """Return True when **all** rules match the context (AND logic)."""
        return all(FeatureFlagEngine._evaluate_rule(r, context) for r in rules)

    @staticmethod
    def _evaluate_rule(rule: TargetingRule, context: dict[str, Any]) -> bool:
        """Evaluate a single targeting rule against the context."""
        ctx_value = context.get(rule.attribute)

        if rule.operator == RuleOperator.EQ:
            return ctx_value == rule.value

        if rule.operator == RuleOperator.NEQ:
            return ctx_value != rule.value

        if rule.operator == RuleOperator.IN:
            if not isinstance(rule.value, (list, tuple, set, frozenset)):
                return False
            return ctx_value in rule.value

        if rule.operator == RuleOperator.CONTAINS:
            if isinstance(ctx_value, str):
                return str(rule.value) in ctx_value
            if isinstance(ctx_value, (list, tuple, set, frozenset)):
                return rule.value in ctx_value
            return False

        return False
