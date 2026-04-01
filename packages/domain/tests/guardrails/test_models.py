"""Unit tests for guardrail domain models."""

from __future__ import annotations

import dataclasses

import pytest

from lintel.domain.guardrails.models import GuardrailAction, GuardrailRule

# ---------------------------------------------------------------------------
# GuardrailAction enum
# ---------------------------------------------------------------------------


class TestGuardrailAction:
    def test_has_warn(self) -> None:
        assert GuardrailAction.WARN == "WARN"

    def test_has_block(self) -> None:
        assert GuardrailAction.BLOCK == "BLOCK"

    def test_has_require_approval(self) -> None:
        assert GuardrailAction.REQUIRE_APPROVAL == "REQUIRE_APPROVAL"

    def test_members_count(self) -> None:
        assert len(GuardrailAction) == 3

    def test_is_str_subclass(self) -> None:
        assert isinstance(GuardrailAction.WARN, str)

    def test_str_value(self) -> None:
        assert str(GuardrailAction.BLOCK) == "BLOCK"


# ---------------------------------------------------------------------------
# GuardrailRule dataclass
# ---------------------------------------------------------------------------


class TestGuardrailRuleConstruction:
    def test_minimal_construction(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="test_rule",
            event_type="RunCompleted",
            condition="rework_rate > threshold",
            action=GuardrailAction.WARN,
        )
        assert rule.rule_id == "r1"
        assert rule.name == "test_rule"
        assert rule.event_type == "RunCompleted"
        assert rule.condition == "rework_rate > threshold"
        assert rule.action == GuardrailAction.WARN

    def test_default_threshold_is_none(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="n",
            event_type="E",
            condition="c",
            action=GuardrailAction.WARN,
        )
        assert rule.threshold is None

    def test_default_cooldown_is_zero(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="n",
            event_type="E",
            condition="c",
            action=GuardrailAction.WARN,
        )
        assert rule.cooldown_seconds == 0

    def test_default_is_default_true(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="n",
            event_type="E",
            condition="c",
            action=GuardrailAction.WARN,
        )
        assert rule.is_default is True

    def test_default_enabled_true(self) -> None:
        rule = GuardrailRule(
            rule_id="r1",
            name="n",
            event_type="E",
            condition="c",
            action=GuardrailAction.WARN,
        )
        assert rule.enabled is True

    def test_explicit_optional_fields(self) -> None:
        rule = GuardrailRule(
            rule_id="r2",
            name="explicit",
            event_type="TestResultRecorded",
            condition="verdict == 'failed'",
            action=GuardrailAction.BLOCK,
            threshold=10.5,
            cooldown_seconds=120,
            is_default=False,
            enabled=False,
        )
        assert rule.threshold == 10.5
        assert rule.cooldown_seconds == 120
        assert rule.is_default is False
        assert rule.enabled is False


class TestGuardrailRuleImmutability:
    @pytest.fixture()
    def rule(self) -> GuardrailRule:
        return GuardrailRule(
            rule_id="r1",
            name="n",
            event_type="E",
            condition="c",
            action=GuardrailAction.WARN,
        )

    def test_frozen_rule_id(self, rule: GuardrailRule) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.rule_id = "changed"  # type: ignore[misc]

    def test_frozen_name(self, rule: GuardrailRule) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.name = "changed"  # type: ignore[misc]

    def test_frozen_enabled(self, rule: GuardrailRule) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.enabled = False  # type: ignore[misc]

    def test_frozen_threshold(self, rule: GuardrailRule) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.threshold = 99.0  # type: ignore[misc]

    def test_frozen_action(self, rule: GuardrailRule) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.action = GuardrailAction.BLOCK  # type: ignore[misc]


class TestGuardrailRuleFieldTypes:
    def test_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(GuardrailRule)

    def test_field_names(self) -> None:
        names = {f.name for f in dataclasses.fields(GuardrailRule)}
        assert names == {
            "rule_id",
            "name",
            "event_type",
            "condition",
            "action",
            "threshold",
            "cooldown_seconds",
            "is_default",
            "enabled",
        }


# ---------------------------------------------------------------------------
# RuleVerdict enum
# ---------------------------------------------------------------------------


class TestRuleVerdict:
    def test_members(self) -> None:
        from lintel.domain.guardrails.models import RuleVerdict

        assert set(RuleVerdict) == {
            RuleVerdict.PASS,
            RuleVerdict.WARN,
            RuleVerdict.FAIL,
            RuleVerdict.ERROR,
        }

    def test_is_str(self) -> None:
        from lintel.domain.guardrails.models import RuleVerdict

        assert isinstance(RuleVerdict.PASS, str)


# ---------------------------------------------------------------------------
# CooldownState
# ---------------------------------------------------------------------------


class TestCooldownState:
    def test_not_in_cooldown_initially(self) -> None:
        from lintel.domain.guardrails.models import CooldownState

        cs = CooldownState()
        assert not cs.in_cooldown("r1", 300, now=100.0)

    def test_in_cooldown_after_record(self) -> None:
        from lintel.domain.guardrails.models import CooldownState

        cs = CooldownState()
        cs.record("r1", now=100.0)
        assert cs.in_cooldown("r1", 300, now=200.0)

    def test_cooldown_expires(self) -> None:
        from lintel.domain.guardrails.models import CooldownState

        cs = CooldownState()
        cs.record("r1", now=100.0)
        assert not cs.in_cooldown("r1", 300, now=500.0)

    def test_zero_cooldown_never_blocks(self) -> None:
        from lintel.domain.guardrails.models import CooldownState

        cs = CooldownState()
        cs.record("r1", now=100.0)
        assert not cs.in_cooldown("r1", 0, now=100.0)

    def test_scoped_cooldown(self) -> None:
        from lintel.domain.guardrails.models import CooldownState

        cs = CooldownState()
        cs.record("r1", now=100.0, scope_key="project-a")
        assert cs.in_cooldown("r1", 300, now=200.0, scope_key="project-a")
        assert not cs.in_cooldown("r1", 300, now=200.0, scope_key="project-b")


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    def test_triggered_rules(self) -> None:
        from lintel.domain.guardrails.models import EvaluationResult, RuleEvaluation, RuleVerdict

        rule = GuardrailRule(
            rule_id="r1", name="n", event_type="E", condition="c", action=GuardrailAction.WARN
        )
        evals = (
            RuleEvaluation(rule=rule, verdict=RuleVerdict.WARN, triggered=True),
            RuleEvaluation(rule=rule, verdict=RuleVerdict.PASS, triggered=False),
        )
        result = EvaluationResult(evaluations=evals, passed=True)
        assert len(result.triggered_rules) == 1
        assert len(result.warnings) == 1
        assert len(result.failures) == 0
