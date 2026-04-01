"""Tests for threshold-based auto-escalation tiers (GRD-2)."""

from __future__ import annotations

import pytest

from lintel.domain.guardrails.escalation import (
    EscalationDecision,
    EscalationEngine,
    EscalationPolicy,
    EscalationTier,
    TierThreshold,
)
from lintel.domain.guardrails.models import (
    EvaluationResult,
    GuardrailAction,
    GuardrailRule,
    RuleEvaluation,
    RuleVerdict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule(
    action: GuardrailAction = GuardrailAction.WARN,
    rule_id: str = "r1",
) -> GuardrailRule:
    return GuardrailRule(
        rule_id=rule_id,
        name=f"Rule {rule_id}",
        event_type="TestEvent",
        condition="x > 0",
        action=action,
    )


def _triggered(
    action: GuardrailAction = GuardrailAction.WARN,
    rule_id: str = "r1",
) -> RuleEvaluation:
    return RuleEvaluation(
        rule=_rule(action, rule_id),
        verdict=RuleVerdict.WARN if action == GuardrailAction.WARN else RuleVerdict.FAIL,
        triggered=True,
        message=f"{action.value}: Rule {rule_id}",
    )


def _result(*evaluations: RuleEvaluation) -> EvaluationResult:
    has_block = any(
        e.triggered and e.rule.action in (GuardrailAction.BLOCK, GuardrailAction.REQUIRE_APPROVAL)
        for e in evaluations
    )
    return EvaluationResult(
        evaluations=tuple(evaluations),
        passed=not has_block,
    )


# ---------------------------------------------------------------------------
# EscalationTier enum
# ---------------------------------------------------------------------------


class TestEscalationTier:
    def test_ordering(self) -> None:
        assert EscalationTier.LOG < EscalationTier.WARN
        assert EscalationTier.WARN < EscalationTier.REQUIRE_APPROVAL
        assert EscalationTier.REQUIRE_APPROVAL < EscalationTier.BLOCK
        assert EscalationTier.BLOCK < EscalationTier.AUTO_REMEDIATE

    def test_int_values(self) -> None:
        assert int(EscalationTier.LOG) == 0
        assert int(EscalationTier.AUTO_REMEDIATE) == 4


# ---------------------------------------------------------------------------
# EscalationPolicy
# ---------------------------------------------------------------------------


class TestEscalationPolicy:
    def test_default_policy_has_action_tiers(self) -> None:
        policy = EscalationPolicy.default()
        assert policy.action_tiers["WARN"] == EscalationTier.WARN
        assert policy.action_tiers["BLOCK"] == EscalationTier.BLOCK
        assert policy.action_tiers["REQUIRE_APPROVAL"] == EscalationTier.REQUIRE_APPROVAL

    def test_default_policy_has_count_thresholds(self) -> None:
        policy = EscalationPolicy.default()
        assert len(policy.count_thresholds) == 3

    def test_custom_policy(self) -> None:
        policy = EscalationPolicy(
            action_tiers={"WARN": EscalationTier.LOG},
            count_thresholds=(TierThreshold(min_triggered=10, tier=EscalationTier.BLOCK),),
        )
        assert policy.action_tiers["WARN"] == EscalationTier.LOG
        assert len(policy.count_thresholds) == 1


# ---------------------------------------------------------------------------
# EscalationEngine — no triggers
# ---------------------------------------------------------------------------


class TestEscalationEngineNoTriggers:
    def test_no_triggered_rules_returns_log_tier(self) -> None:
        engine = EscalationEngine()
        result = _result()
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.LOG
        assert decision.triggered_count == 0
        assert not decision.should_notify
        assert not decision.should_pause
        assert not decision.should_block
        assert not decision.should_remediate


# ---------------------------------------------------------------------------
# EscalationEngine — action-based escalation
# ---------------------------------------------------------------------------


class TestEscalationEngineActionBased:
    def test_warn_action_gives_warn_tier(self) -> None:
        engine = EscalationEngine()
        result = _result(_triggered(GuardrailAction.WARN))
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.WARN
        assert decision.should_notify
        assert not decision.should_pause
        assert not decision.should_block

    def test_require_approval_gives_require_approval_tier(self) -> None:
        engine = EscalationEngine()
        result = _result(_triggered(GuardrailAction.REQUIRE_APPROVAL, "r1"))
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.REQUIRE_APPROVAL
        assert decision.should_notify
        assert decision.should_pause
        assert not decision.should_block

    def test_block_action_gives_block_tier(self) -> None:
        engine = EscalationEngine()
        result = _result(_triggered(GuardrailAction.BLOCK, "r1"))
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.BLOCK
        assert decision.should_notify
        assert decision.should_pause
        assert decision.should_block
        assert not decision.should_remediate


# ---------------------------------------------------------------------------
# EscalationEngine — count-based escalation
# ---------------------------------------------------------------------------


class TestEscalationEngineCountBased:
    def test_three_warn_rules_escalate_to_require_approval(self) -> None:
        engine = EscalationEngine()
        evals = [_triggered(GuardrailAction.WARN, f"r{i}") for i in range(3)]
        result = _result(*evals)
        decision = engine.decide(result)

        # 3 WARN rules: action_tier=WARN, count_tier=REQUIRE_APPROVAL
        assert decision.tier == EscalationTier.REQUIRE_APPROVAL
        assert decision.should_pause

    def test_five_warn_rules_escalate_to_block(self) -> None:
        engine = EscalationEngine()
        evals = [_triggered(GuardrailAction.WARN, f"r{i}") for i in range(5)]
        result = _result(*evals)
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.BLOCK
        assert decision.should_block


# ---------------------------------------------------------------------------
# EscalationEngine — max(action, count)
# ---------------------------------------------------------------------------


class TestEscalationEngineMaxTier:
    def test_block_action_wins_over_low_count(self) -> None:
        engine = EscalationEngine()
        result = _result(_triggered(GuardrailAction.BLOCK, "r1"))
        decision = engine.decide(result)

        # 1 BLOCK: action_tier=BLOCK, count_tier=WARN → max=BLOCK
        assert decision.tier == EscalationTier.BLOCK

    def test_high_count_wins_over_warn_action(self) -> None:
        engine = EscalationEngine()
        evals = [_triggered(GuardrailAction.WARN, f"r{i}") for i in range(5)]
        result = _result(*evals)
        decision = engine.decide(result)

        # 5 WARN: action_tier=WARN, count_tier=BLOCK → max=BLOCK
        assert decision.tier == EscalationTier.BLOCK


# ---------------------------------------------------------------------------
# EscalationEngine — custom policy
# ---------------------------------------------------------------------------


class TestEscalationEngineCustomPolicy:
    def test_custom_action_tier(self) -> None:
        policy = EscalationPolicy(
            action_tiers={"WARN": EscalationTier.AUTO_REMEDIATE},
            count_thresholds=(),
        )
        engine = EscalationEngine(policy)
        result = _result(_triggered(GuardrailAction.WARN))
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.AUTO_REMEDIATE
        assert decision.should_remediate

    def test_custom_count_threshold(self) -> None:
        policy = EscalationPolicy(
            action_tiers={"WARN": EscalationTier.LOG},
            count_thresholds=(TierThreshold(min_triggered=2, tier=EscalationTier.AUTO_REMEDIATE),),
        )
        engine = EscalationEngine(policy)
        evals = [_triggered(GuardrailAction.WARN, f"r{i}") for i in range(2)]
        result = _result(*evals)
        decision = engine.decide(result)

        assert decision.tier == EscalationTier.AUTO_REMEDIATE


# ---------------------------------------------------------------------------
# EscalationEngine — tier_for_action helper
# ---------------------------------------------------------------------------


class TestTierForAction:
    def test_known_actions(self) -> None:
        engine = EscalationEngine()
        assert engine.tier_for_action(GuardrailAction.WARN) == EscalationTier.WARN
        assert engine.tier_for_action(GuardrailAction.BLOCK) == EscalationTier.BLOCK
        assert (
            engine.tier_for_action(GuardrailAction.REQUIRE_APPROVAL)
            == EscalationTier.REQUIRE_APPROVAL
        )


# ---------------------------------------------------------------------------
# EscalationDecision flags
# ---------------------------------------------------------------------------


class TestEscalationDecisionFlags:
    @pytest.mark.parametrize(
        ("tier", "notify", "pause", "block", "remediate"),
        [
            (EscalationTier.LOG, False, False, False, False),
            (EscalationTier.WARN, True, False, False, False),
            (EscalationTier.REQUIRE_APPROVAL, True, True, False, False),
            (EscalationTier.BLOCK, True, True, True, False),
            (EscalationTier.AUTO_REMEDIATE, True, True, True, True),
        ],
    )
    def test_flag_combinations(
        self,
        tier: EscalationTier,
        notify: bool,
        pause: bool,
        block: bool,
        remediate: bool,
    ) -> None:
        decision = EscalationDecision(
            tier=tier,
            reason="test",
            triggered_count=1,
            should_notify=tier >= EscalationTier.WARN,
            should_pause=tier >= EscalationTier.REQUIRE_APPROVAL,
            should_block=tier >= EscalationTier.BLOCK,
            should_remediate=tier >= EscalationTier.AUTO_REMEDIATE,
        )
        assert decision.should_notify == notify
        assert decision.should_pause == pause
        assert decision.should_block == block
        assert decision.should_remediate == remediate


# ---------------------------------------------------------------------------
# Integration: GuardrailEngine attaches escalation to EvaluationResult
# ---------------------------------------------------------------------------


class TestEngineIntegration:
    def test_evaluate_attaches_escalation_decision(self) -> None:
        from lintel.domain.guardrails.engine import GuardrailEngine
        from lintel.domain.guardrails.escalation import EscalationDecision

        class FakeRepo:
            async def list_enabled(self) -> list[GuardrailRule]:
                return []

            async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
                return []

            async def get(self, rule_id: str) -> GuardrailRule | None:
                return None

            async def upsert(self, rule: GuardrailRule) -> None:
                pass

            async def delete(self, rule_id: str) -> bool:
                return False

        engine = GuardrailEngine(rule_repo=FakeRepo())
        rules = [_rule(GuardrailAction.WARN)]
        result = engine.evaluate(rules, {"x": 1})

        assert result.escalation is not None
        assert isinstance(result.escalation, EscalationDecision)
        assert result.escalation.tier == EscalationTier.WARN

    def test_evaluate_no_triggers_has_log_escalation(self) -> None:
        from lintel.domain.guardrails.engine import GuardrailEngine
        from lintel.domain.guardrails.escalation import EscalationDecision

        class FakeRepo:
            async def list_enabled(self) -> list[GuardrailRule]:
                return []

            async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
                return []

            async def get(self, rule_id: str) -> GuardrailRule | None:
                return None

            async def upsert(self, rule: GuardrailRule) -> None:
                pass

            async def delete(self, rule_id: str) -> bool:
                return False

        engine = GuardrailEngine(rule_repo=FakeRepo())
        rules = [_rule(GuardrailAction.WARN)]
        result = engine.evaluate(rules, {"x": -1})

        assert result.escalation is not None
        assert isinstance(result.escalation, EscalationDecision)
        assert result.escalation.tier == EscalationTier.LOG
