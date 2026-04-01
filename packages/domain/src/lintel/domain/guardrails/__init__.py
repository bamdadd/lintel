"""Guardrail rule domain models, default rules, and evaluation engine (GRD-7)."""

from lintel.domain.guardrails.cost_rules import (
    COST_GUARDRAIL_RULES,
    CostBudget,
    CostGuardrailChecker,
    CostSnapshot,
    build_cost_context,
)
from lintel.domain.guardrails.default_rules import DEFAULT_RULES
from lintel.domain.guardrails.engine import GuardrailBlockError, GuardrailEngine
from lintel.domain.guardrails.escalation import (
    EscalationDecision,
    EscalationEngine,
    EscalationPolicy,
    EscalationTier,
    TierThreshold,
)
from lintel.domain.guardrails.evaluator import evaluate_condition
from lintel.domain.guardrails.models import (
    CooldownState,
    EvaluationResult,
    GuardrailAction,
    GuardrailRule,
    RuleEvaluation,
    RuleVerdict,
)

__all__ = [
    "COST_GUARDRAIL_RULES",
    "DEFAULT_RULES",
    "CooldownState",
    "CostBudget",
    "CostGuardrailChecker",
    "CostSnapshot",
    "EscalationDecision",
    "EscalationEngine",
    "EscalationPolicy",
    "EscalationTier",
    "EvaluationResult",
    "GuardrailAction",
    "GuardrailBlockError",
    "GuardrailEngine",
    "GuardrailRule",
    "RuleEvaluation",
    "RuleVerdict",
    "TierThreshold",
    "build_cost_context",
    "evaluate_condition",
]
