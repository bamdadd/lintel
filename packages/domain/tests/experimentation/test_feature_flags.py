"""Tests for feature flags and A/B testing domain model."""

from __future__ import annotations

import pytest

from lintel.domain.experimentation.feature_flags import (
    ABTest,
    FeatureFlag,
    FeatureFlagEngine,
    RuleOperator,
    TargetingRule,
    Variant,
    _hash_key,
)


@pytest.fixture
def engine() -> FeatureFlagEngine:
    return FeatureFlagEngine()


# ---------------------------------------------------------------------------
# FeatureFlag dataclass tests
# ---------------------------------------------------------------------------


class TestFeatureFlagDataclass:
    def test_defaults(self) -> None:
        flag = FeatureFlag(id="f1", name="my-flag")
        assert flag.enabled is False
        assert flag.rollout_percentage == 100.0
        assert flag.targeting_rules == []

    def test_frozen(self) -> None:
        flag = FeatureFlag(id="f1", name="my-flag", enabled=True)
        with pytest.raises(AttributeError):
            flag.enabled = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TargetingRule tests
# ---------------------------------------------------------------------------


class TestTargetingRule:
    def test_eq(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="country", operator=RuleOperator.EQ, value="US")
        assert engine._evaluate_rule(rule, {"country": "US"}) is True
        assert engine._evaluate_rule(rule, {"country": "UK"}) is False

    def test_neq(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="env", operator=RuleOperator.NEQ, value="prod")
        assert engine._evaluate_rule(rule, {"env": "staging"}) is True
        assert engine._evaluate_rule(rule, {"env": "prod"}) is False

    def test_in_operator(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="tier", operator=RuleOperator.IN, value=["gold", "platinum"])
        assert engine._evaluate_rule(rule, {"tier": "gold"}) is True
        assert engine._evaluate_rule(rule, {"tier": "silver"}) is False

    def test_in_with_non_list_value(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="tier", operator=RuleOperator.IN, value="not-a-list")
        assert engine._evaluate_rule(rule, {"tier": "n"}) is False

    def test_contains_string(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="email", operator=RuleOperator.CONTAINS, value="@acme")
        assert engine._evaluate_rule(rule, {"email": "alice@acme.com"}) is True
        assert engine._evaluate_rule(rule, {"email": "bob@other.com"}) is False

    def test_contains_list(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="tags", operator=RuleOperator.CONTAINS, value="beta")
        assert engine._evaluate_rule(rule, {"tags": ["beta", "internal"]}) is True
        assert engine._evaluate_rule(rule, {"tags": ["stable"]}) is False

    def test_contains_unsupported_type(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="count", operator=RuleOperator.CONTAINS, value=1)
        assert engine._evaluate_rule(rule, {"count": 42}) is False

    def test_missing_attribute(self, engine: FeatureFlagEngine) -> None:
        rule = TargetingRule(attribute="missing", operator=RuleOperator.EQ, value="x")
        assert engine._evaluate_rule(rule, {}) is False


# ---------------------------------------------------------------------------
# is_enabled tests
# ---------------------------------------------------------------------------


class TestIsEnabled:
    def test_disabled_flag(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="off", enabled=False)
        assert engine.is_enabled(flag, {"user_id": "u1"}) is False

    def test_enabled_full_rollout(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="on", enabled=True, rollout_percentage=100.0)
        assert engine.is_enabled(flag, {"user_id": "u1"}) is True

    def test_zero_rollout(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="zero", enabled=True, rollout_percentage=0.0)
        assert engine.is_enabled(flag, {"user_id": "u1"}) is False

    def test_partial_rollout_deterministic(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="half", enabled=True, rollout_percentage=50.0)
        result1 = engine.is_enabled(flag, {"user_id": "u1"})
        result2 = engine.is_enabled(flag, {"user_id": "u1"})
        assert result1 == result2  # deterministic

    def test_partial_rollout_splits_users(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="half", enabled=True, rollout_percentage=50.0)
        results = [engine.is_enabled(flag, {"user_id": f"u{i}"}) for i in range(1000)]
        enabled_count = sum(results)
        # With 50% rollout over 1000 users, should be roughly 500 (allow wide margin)
        assert 300 < enabled_count < 700

    def test_targeting_rules_block(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(
            id="f1",
            name="targeted",
            enabled=True,
            targeting_rules=[
                TargetingRule(attribute="country", operator=RuleOperator.EQ, value="US")
            ],
        )
        assert engine.is_enabled(flag, {"user_id": "u1", "country": "US"}) is True
        assert engine.is_enabled(flag, {"user_id": "u1", "country": "UK"}) is False

    def test_multiple_rules_all_must_match(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(
            id="f1",
            name="multi",
            enabled=True,
            targeting_rules=[
                TargetingRule(attribute="country", operator=RuleOperator.EQ, value="US"),
                TargetingRule(attribute="tier", operator=RuleOperator.EQ, value="gold"),
            ],
        )
        assert engine.is_enabled(flag, {"user_id": "u1", "country": "US", "tier": "gold"})
        assert not engine.is_enabled(flag, {"user_id": "u1", "country": "US", "tier": "silver"})

    def test_fallback_to_id_key(self, engine: FeatureFlagEngine) -> None:
        flag = FeatureFlag(id="f1", name="fb", enabled=True, rollout_percentage=50.0)
        # Should not raise when user_id absent but id present
        engine.is_enabled(flag, {"id": "some-id"})


# ---------------------------------------------------------------------------
# A/B test variant assignment
# ---------------------------------------------------------------------------


class TestGetVariant:
    def test_no_variants_raises(self, engine: FeatureFlagEngine) -> None:
        test = ABTest(id="t1", name="empty")
        with pytest.raises(ValueError, match="no variants"):
            engine.get_variant(test, {"user_id": "u1"})

    def test_deterministic_assignment(self, engine: FeatureFlagEngine) -> None:
        variants = [Variant(id="a", name="A"), Variant(id="b", name="B")]
        test = ABTest(id="t1", name="ab", variants=variants, traffic_allocation={"a": 50, "b": 50})
        v1 = engine.get_variant(test, {"user_id": "u1"})
        v2 = engine.get_variant(test, {"user_id": "u1"})
        assert v1 == v2

    def test_weighted_allocation(self, engine: FeatureFlagEngine) -> None:
        variants = [Variant(id="a", name="A"), Variant(id="b", name="B")]
        test = ABTest(
            id="t1", name="weighted", variants=variants, traffic_allocation={"a": 90, "b": 10}
        )
        counts: dict[str, int] = {"a": 0, "b": 0}
        for i in range(1000):
            v = engine.get_variant(test, {"user_id": f"u{i}"})
            counts[v.id] += 1
        # 90/10 split — variant A should dominate
        assert counts["a"] > counts["b"]
        assert counts["a"] > 700

    def test_equal_split_no_allocation(self, engine: FeatureFlagEngine) -> None:
        variants = [Variant(id="a", name="A"), Variant(id="b", name="B")]
        test = ABTest(id="t1", name="equal", variants=variants)
        counts: dict[str, int] = {"a": 0, "b": 0}
        for i in range(1000):
            v = engine.get_variant(test, {"user_id": f"u{i}"})
            counts[v.id] += 1
        assert counts["a"] > 300
        assert counts["b"] > 300

    def test_variant_config(self) -> None:
        v = Variant(id="v1", name="V1", config={"color": "red"})
        assert v.config["color"] == "red"

    def test_variant_frozen(self) -> None:
        v = Variant(id="v1", name="V1")
        with pytest.raises(AttributeError):
            v.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Hash key utility
# ---------------------------------------------------------------------------


class TestHashKey:
    def test_range(self) -> None:
        for i in range(100):
            h = _hash_key("flag", f"user_{i}")
            assert 0.0 <= h < 100.0

    def test_deterministic(self) -> None:
        assert _hash_key("f1", "u1") == _hash_key("f1", "u1")

    def test_different_inputs(self) -> None:
        assert _hash_key("f1", "u1") != _hash_key("f1", "u2")
