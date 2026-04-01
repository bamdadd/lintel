"""Cost guardrail rules — token budgets and real-time enforcement (GRD-4).

Provides :class:`CostBudget` for configuring spend limits and
:class:`CostGuardrailChecker` for evaluating current spend against budgets.
Also exports pre-built :data:`COST_GUARDRAIL_RULES` ready to seed into the
guardrail engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lintel.domain.guardrails.models import (
    EvaluationResult,
    GuardrailAction,
    GuardrailRule,
    RuleEvaluation,
    RuleVerdict,
)

# ---------------------------------------------------------------------------
# CostBudget — budget configuration dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostBudget:
    """Token and cost budget for a pipeline run or scope.

    Attributes:
        max_tokens: Hard cap on total tokens (input + output) for the scope.
            ``0`` means unlimited.
        max_cost_usd: Hard cap on total USD spend. ``0.0`` means unlimited.
        per_step_limit_usd: Maximum USD spend for any single pipeline step.
            ``0.0`` means unlimited.
        warning_threshold_pct: Percentage (0-100) of the budget at which a
            warning is emitted.  E.g. ``80`` means warn at 80 % spend.
    """

    max_tokens: int = 0
    max_cost_usd: float = 0.0
    per_step_limit_usd: float = 0.0
    warning_threshold_pct: float = 80.0


# ---------------------------------------------------------------------------
# CostSnapshot — tracks accumulated spend for a scope
# ---------------------------------------------------------------------------


@dataclass
class CostSnapshot:
    """Accumulated cost/token state for a scope (run, project, etc.)."""

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    per_step_costs: dict[str, float] = field(default_factory=dict)
    per_step_tokens: dict[str, int] = field(default_factory=dict)

    def record(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        step: str = "",
    ) -> None:
        """Record a model call's cost and token usage."""
        tokens = input_tokens + output_tokens
        self.total_tokens += tokens
        self.total_cost_usd += cost_usd
        if step:
            self.per_step_costs[step] = self.per_step_costs.get(step, 0.0) + cost_usd
            self.per_step_tokens[step] = self.per_step_tokens.get(step, 0) + tokens


# ---------------------------------------------------------------------------
# CostGuardrailChecker
# ---------------------------------------------------------------------------


class CostGuardrailChecker:
    """Evaluates current spend against a :class:`CostBudget`.

    The checker produces :class:`RuleEvaluation` entries for each budget
    dimension that is violated or approaching its limit.
    """

    def evaluate(
        self,
        budget: CostBudget,
        snapshot: CostSnapshot,
        *,
        current_step: str = "",
    ) -> EvaluationResult:
        """Check *snapshot* against *budget* and return structured results.

        Args:
            budget: The budget to enforce.
            snapshot: Accumulated spend so far.
            current_step: If provided, also checks per-step limit against this step.

        Returns:
            :class:`EvaluationResult` with per-check verdicts.
        """
        evaluations: list[RuleEvaluation] = []
        has_block = False

        # --- Total token budget ---
        if budget.max_tokens > 0:
            eval_, blocked = self._check_threshold(
                name="total_token_budget",
                current=float(snapshot.total_tokens),
                limit=float(budget.max_tokens),
                warning_pct=budget.warning_threshold_pct,
                unit="tokens",
            )
            evaluations.extend(eval_)
            has_block = has_block or blocked

        # --- Total cost budget ---
        if budget.max_cost_usd > 0.0:
            eval_, blocked = self._check_threshold(
                name="total_cost_budget",
                current=snapshot.total_cost_usd,
                limit=budget.max_cost_usd,
                warning_pct=budget.warning_threshold_pct,
                unit="USD",
            )
            evaluations.extend(eval_)
            has_block = has_block or blocked

        # --- Per-step cost limit ---
        if budget.per_step_limit_usd > 0.0 and current_step:
            step_cost = snapshot.per_step_costs.get(current_step, 0.0)
            eval_, blocked = self._check_threshold(
                name=f"step_cost:{current_step}",
                current=step_cost,
                limit=budget.per_step_limit_usd,
                warning_pct=budget.warning_threshold_pct,
                unit="USD",
            )
            evaluations.extend(eval_)
            has_block = has_block or blocked

        # If nothing was checked, emit a single PASS
        if not evaluations:
            evaluations.append(
                RuleEvaluation(
                    rule=_NOOP_RULE,
                    verdict=RuleVerdict.PASS,
                    triggered=False,
                    message="No budget limits configured",
                )
            )

        return EvaluationResult(
            evaluations=tuple(evaluations),
            passed=not has_block,
        )

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    @staticmethod
    def _check_threshold(
        *,
        name: str,
        current: float,
        limit: float,
        warning_pct: float,
        unit: str,
    ) -> tuple[list[RuleEvaluation], bool]:
        """Return evaluations for a single budget dimension."""
        evals: list[RuleEvaluation] = []
        blocked = False
        rule = _make_rule(name)

        if current >= limit:
            evals.append(
                RuleEvaluation(
                    rule=rule,
                    verdict=RuleVerdict.FAIL,
                    triggered=True,
                    message=f"BLOCK: {name} exceeded — {current:.4g} / {limit:.4g} {unit}",
                )
            )
            blocked = True
        elif warning_pct > 0 and current >= limit * (warning_pct / 100.0):
            pct = (current / limit) * 100.0
            evals.append(
                RuleEvaluation(
                    rule=rule,
                    verdict=RuleVerdict.WARN,
                    triggered=True,
                    message=(f"WARN: {name} at {pct:.1f}% — {current:.4g} / {limit:.4g} {unit}"),
                )
            )
        else:
            evals.append(
                RuleEvaluation(
                    rule=rule,
                    verdict=RuleVerdict.PASS,
                    triggered=False,
                )
            )

        return evals, blocked


# ---------------------------------------------------------------------------
# Helper to synthesise lightweight rules for cost checks
# ---------------------------------------------------------------------------

_NOOP_RULE = GuardrailRule(
    rule_id="cost-noop",
    name="cost_noop",
    event_type="ModelCallCompleted",
    condition="true == true",
    action=GuardrailAction.WARN,
    enabled=True,
)


def _make_rule(name: str) -> GuardrailRule:
    return GuardrailRule(
        rule_id=f"cost-{name}",
        name=name,
        event_type="ModelCallCompleted",
        condition="true == true",
        action=GuardrailAction.BLOCK,
        enabled=True,
    )


# ---------------------------------------------------------------------------
# Pre-built cost guardrail rules for the engine (GRD-4.3)
# ---------------------------------------------------------------------------


def build_cost_context(snapshot: CostSnapshot, *, step: str = "") -> dict[str, Any]:
    """Build a context dict suitable for the generic guardrail evaluator.

    This bridges :class:`CostSnapshot` into the expression evaluator so that
    pre-built cost rules (below) can be evaluated by :class:`GuardrailEngine`.
    """
    ctx: dict[str, Any] = {
        "total_tokens": snapshot.total_tokens,
        "total_cost_usd": snapshot.total_cost_usd,
    }
    if step:
        ctx["step_cost_usd"] = snapshot.per_step_costs.get(step, 0.0)
        ctx["step_tokens"] = snapshot.per_step_tokens.get(step, 0)
    return ctx


COST_GUARDRAIL_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        rule_id="cost-step-usd-warning",
        name="step_cost_warning",
        event_type="ModelCallCompleted",
        condition="step_cost_usd > threshold",
        action=GuardrailAction.WARN,
        threshold=1.0,
        cooldown_seconds=60,
        is_default=True,
        enabled=True,
    ),
    GuardrailRule(
        rule_id="cost-total-tokens-block",
        name="total_token_limit",
        event_type="ModelCallCompleted",
        condition="total_tokens > threshold",
        action=GuardrailAction.BLOCK,
        threshold=100_000.0,
        cooldown_seconds=0,
        is_default=True,
        enabled=True,
    ),
    GuardrailRule(
        rule_id="cost-run-usd-warning",
        name="run_cost_usd_warning",
        event_type="ModelCallCompleted",
        condition="total_cost_usd > threshold",
        action=GuardrailAction.WARN,
        threshold=5.0,
        cooldown_seconds=300,
        is_default=True,
        enabled=True,
    ),
    GuardrailRule(
        rule_id="cost-run-usd-block",
        name="run_cost_usd_block",
        event_type="ModelCallCompleted",
        condition="total_cost_usd > threshold",
        action=GuardrailAction.BLOCK,
        threshold=50.0,
        cooldown_seconds=0,
        is_default=True,
        enabled=True,
    ),
)
