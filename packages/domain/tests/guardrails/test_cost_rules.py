"""Tests for cost guardrail rules (GRD-4)."""

from __future__ import annotations

from lintel.domain.guardrails.cost_rules import (
    COST_GUARDRAIL_RULES,
    CostBudget,
    CostGuardrailChecker,
    CostSnapshot,
    build_cost_context,
)
from lintel.domain.guardrails.evaluator import evaluate_condition
from lintel.domain.guardrails.models import RuleVerdict

# ---------------------------------------------------------------------------
# CostBudget
# ---------------------------------------------------------------------------


class TestCostBudget:
    def test_defaults(self) -> None:
        budget = CostBudget()
        assert budget.max_tokens == 0
        assert budget.max_cost_usd == 0.0
        assert budget.per_step_limit_usd == 0.0
        assert budget.warning_threshold_pct == 80.0

    def test_custom_values(self) -> None:
        budget = CostBudget(
            max_tokens=50_000,
            max_cost_usd=10.0,
            per_step_limit_usd=2.0,
            warning_threshold_pct=70.0,
        )
        assert budget.max_tokens == 50_000
        assert budget.max_cost_usd == 10.0
        assert budget.per_step_limit_usd == 2.0
        assert budget.warning_threshold_pct == 70.0

    def test_frozen(self) -> None:
        budget = CostBudget(max_tokens=100)
        try:
            budget.max_tokens = 200  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("CostBudget should be frozen")


# ---------------------------------------------------------------------------
# CostSnapshot
# ---------------------------------------------------------------------------


class TestCostSnapshot:
    def test_record_accumulates(self) -> None:
        snap = CostSnapshot()
        snap.record(input_tokens=100, output_tokens=50, cost_usd=0.01, step="research")
        snap.record(input_tokens=200, output_tokens=100, cost_usd=0.02, step="research")
        snap.record(input_tokens=50, output_tokens=25, cost_usd=0.005, step="implement")

        assert snap.total_tokens == 525
        assert abs(snap.total_cost_usd - 0.035) < 1e-9
        assert abs(snap.per_step_costs["research"] - 0.03) < 1e-9
        assert snap.per_step_costs["implement"] == 0.005
        assert snap.per_step_tokens["research"] == 450
        assert snap.per_step_tokens["implement"] == 75

    def test_record_no_step(self) -> None:
        snap = CostSnapshot()
        snap.record(input_tokens=10, output_tokens=5, cost_usd=0.001)
        assert snap.total_tokens == 15
        assert snap.per_step_costs == {}


# ---------------------------------------------------------------------------
# CostGuardrailChecker
# ---------------------------------------------------------------------------


class TestCostGuardrailChecker:
    def setup_method(self) -> None:
        self.checker = CostGuardrailChecker()

    def test_no_limits_configured(self) -> None:
        result = self.checker.evaluate(CostBudget(), CostSnapshot())
        assert result.passed
        assert len(result.evaluations) == 1
        assert result.evaluations[0].verdict == RuleVerdict.PASS
        assert "No budget limits" in result.evaluations[0].message

    def test_under_budget_passes(self) -> None:
        budget = CostBudget(max_tokens=100_000, max_cost_usd=10.0)
        snap = CostSnapshot(total_tokens=1000, total_cost_usd=0.50)
        result = self.checker.evaluate(budget, snap)
        assert result.passed
        assert len(result.failures) == 0
        assert len(result.warnings) == 0

    def test_token_budget_exceeded_blocks(self) -> None:
        budget = CostBudget(max_tokens=10_000)
        snap = CostSnapshot(total_tokens=10_001)
        result = self.checker.evaluate(budget, snap)
        assert not result.passed
        assert len(result.failures) == 1
        assert "total_token_budget" in result.failures[0].message

    def test_cost_budget_exceeded_blocks(self) -> None:
        budget = CostBudget(max_cost_usd=5.0)
        snap = CostSnapshot(total_cost_usd=5.01)
        result = self.checker.evaluate(budget, snap)
        assert not result.passed
        assert len(result.failures) == 1
        assert "total_cost_budget" in result.failures[0].message

    def test_warning_threshold(self) -> None:
        budget = CostBudget(max_cost_usd=10.0, warning_threshold_pct=80.0)
        snap = CostSnapshot(total_cost_usd=8.5)
        result = self.checker.evaluate(budget, snap)
        assert result.passed  # warning doesn't block
        assert len(result.warnings) == 1
        assert "85.0%" in result.warnings[0].message

    def test_warning_threshold_not_reached(self) -> None:
        budget = CostBudget(max_cost_usd=10.0, warning_threshold_pct=80.0)
        snap = CostSnapshot(total_cost_usd=7.0)
        result = self.checker.evaluate(budget, snap)
        assert result.passed
        assert len(result.warnings) == 0

    def test_per_step_limit_exceeded(self) -> None:
        budget = CostBudget(per_step_limit_usd=1.0)
        snap = CostSnapshot(per_step_costs={"implement": 1.50})
        result = self.checker.evaluate(budget, snap, current_step="implement")
        assert not result.passed
        assert len(result.failures) == 1
        assert "step_cost:implement" in result.failures[0].message

    def test_per_step_limit_no_step_name(self) -> None:
        """Per-step limit is skipped when no current_step is provided."""
        budget = CostBudget(per_step_limit_usd=1.0)
        snap = CostSnapshot(per_step_costs={"implement": 5.0})
        result = self.checker.evaluate(budget, snap)
        # No step provided so per-step check is skipped; only the noop rule appears
        assert result.passed

    def test_multiple_violations(self) -> None:
        budget = CostBudget(max_tokens=1000, max_cost_usd=1.0, per_step_limit_usd=0.5)
        snap = CostSnapshot(
            total_tokens=2000,
            total_cost_usd=2.0,
            per_step_costs={"research": 0.8},
        )
        result = self.checker.evaluate(budget, snap, current_step="research")
        assert not result.passed
        assert len(result.failures) == 3

    def test_exact_limit_blocks(self) -> None:
        budget = CostBudget(max_tokens=100)
        snap = CostSnapshot(total_tokens=100)
        result = self.checker.evaluate(budget, snap)
        assert not result.passed

    def test_zero_warning_threshold_skips_warning(self) -> None:
        budget = CostBudget(max_cost_usd=10.0, warning_threshold_pct=0.0)
        snap = CostSnapshot(total_cost_usd=9.0)
        result = self.checker.evaluate(budget, snap)
        assert result.passed
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# build_cost_context + pre-built rules via engine evaluator
# ---------------------------------------------------------------------------


class TestBuildCostContext:
    def test_basic_context(self) -> None:
        snap = CostSnapshot(total_tokens=5000, total_cost_usd=1.23)
        ctx = build_cost_context(snap)
        assert ctx["total_tokens"] == 5000
        assert ctx["total_cost_usd"] == 1.23
        assert "step_cost_usd" not in ctx

    def test_context_with_step(self) -> None:
        snap = CostSnapshot(
            total_tokens=5000,
            total_cost_usd=1.23,
            per_step_costs={"review": 0.45},
            per_step_tokens={"review": 2000},
        )
        ctx = build_cost_context(snap, step="review")
        assert ctx["step_cost_usd"] == 0.45
        assert ctx["step_tokens"] == 2000

    def test_missing_step_defaults_to_zero(self) -> None:
        snap = CostSnapshot()
        ctx = build_cost_context(snap, step="unknown")
        assert ctx["step_cost_usd"] == 0.0
        assert ctx["step_tokens"] == 0


class TestPreBuiltCostRules:
    """Verify pre-built rules work with the expression evaluator."""

    def test_step_cost_warning_triggers(self) -> None:
        rule = COST_GUARDRAIL_RULES[0]
        assert rule.name == "step_cost_warning"
        snap = CostSnapshot(per_step_costs={"impl": 1.50})
        ctx = build_cost_context(snap, step="impl")
        assert evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_step_cost_warning_below(self) -> None:
        rule = COST_GUARDRAIL_RULES[0]
        snap = CostSnapshot(per_step_costs={"impl": 0.50})
        ctx = build_cost_context(snap, step="impl")
        assert not evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_total_token_block_triggers(self) -> None:
        rule = COST_GUARDRAIL_RULES[1]
        assert rule.name == "total_token_limit"
        snap = CostSnapshot(total_tokens=150_000)
        ctx = build_cost_context(snap)
        assert evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_total_token_block_below(self) -> None:
        rule = COST_GUARDRAIL_RULES[1]
        snap = CostSnapshot(total_tokens=50_000)
        ctx = build_cost_context(snap)
        assert not evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_run_cost_warning_triggers(self) -> None:
        rule = COST_GUARDRAIL_RULES[2]
        assert rule.name == "run_cost_usd_warning"
        snap = CostSnapshot(total_cost_usd=6.0)
        ctx = build_cost_context(snap)
        assert evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_run_cost_block_triggers(self) -> None:
        rule = COST_GUARDRAIL_RULES[3]
        assert rule.name == "run_cost_usd_block"
        snap = CostSnapshot(total_cost_usd=55.0)
        ctx = build_cost_context(snap)
        assert evaluate_condition(rule.condition, ctx, threshold=rule.threshold)

    def test_all_rules_have_model_call_event_type(self) -> None:
        for rule in COST_GUARDRAIL_RULES:
            assert rule.event_type == "ModelCallCompleted"

    def test_all_rules_enabled_by_default(self) -> None:
        for rule in COST_GUARDRAIL_RULES:
            assert rule.enabled
            assert rule.is_default
