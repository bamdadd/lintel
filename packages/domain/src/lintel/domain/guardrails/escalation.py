"""Threshold-based auto-escalation tiers (GRD-2).

When guardrail rules fire, the escalation engine determines the appropriate
response tier based on severity and rule-count thresholds defined in an
:class:`EscalationPolicy`.

Tiers (from the GRD-2 spec):

| Tier | Action             | Effect                                      |
|------|--------------------|---------------------------------------------|
| 0    | ``LOG``            | Log only — no user-visible side-effect      |
| 1    | ``WARN``           | Log + notify team channel                   |
| 2    | ``REQUIRE_APPROVAL``| Pause workflow, request human approval      |
| 3    | ``BLOCK``          | Block execution, escalate to team lead      |
| 4    | ``AUTO_REMEDIATE`` | Emergency stop, kill sandbox, notify admin   |
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.guardrails.models import EvaluationResult, GuardrailAction


class EscalationTier(IntEnum):
    """Ordered escalation tiers — higher value means more severe."""

    LOG = 0
    WARN = 1
    REQUIRE_APPROVAL = 2
    BLOCK = 3
    AUTO_REMEDIATE = 4


@dataclass(frozen=True)
class TierThreshold:
    """Maps a minimum triggered-rule count to an escalation tier."""

    min_triggered: int
    tier: EscalationTier


@dataclass(frozen=True)
class EscalationPolicy:
    """Defines how evaluation results map to escalation tiers.

    The policy uses two dimensions:

    1. **Action severity** — each :class:`GuardrailAction` maps to a default
       tier via :attr:`action_tiers`.
    2. **Rule-count thresholds** — if the number of triggered rules exceeds
       certain counts the tier is escalated further via :attr:`count_thresholds`.

    The final tier is ``max(action_tier, count_tier)``.
    """

    action_tiers: dict[str, EscalationTier] = field(default_factory=dict)
    count_thresholds: tuple[TierThreshold, ...] = ()

    @staticmethod
    def default() -> EscalationPolicy:
        """Return the built-in default policy matching the GRD-2 spec."""
        return EscalationPolicy(
            action_tiers={
                "WARN": EscalationTier.WARN,
                "REQUIRE_APPROVAL": EscalationTier.REQUIRE_APPROVAL,
                "BLOCK": EscalationTier.BLOCK,
            },
            count_thresholds=(
                TierThreshold(min_triggered=1, tier=EscalationTier.WARN),
                TierThreshold(min_triggered=3, tier=EscalationTier.REQUIRE_APPROVAL),
                TierThreshold(min_triggered=5, tier=EscalationTier.BLOCK),
            ),
        )


@dataclass(frozen=True)
class EscalationDecision:
    """The outcome of running an :class:`EvaluationResult` through the escalation engine."""

    tier: EscalationTier
    reason: str
    triggered_count: int
    should_notify: bool
    should_pause: bool
    should_block: bool
    should_remediate: bool


class EscalationEngine:
    """Determines escalation actions from guardrail evaluation results.

    Usage::

        engine = EscalationEngine()  # uses default policy
        decision = engine.decide(evaluation_result)
        if decision.should_block:
            ...
    """

    def __init__(self, policy: EscalationPolicy | None = None) -> None:
        self._policy = policy or EscalationPolicy.default()

    @property
    def policy(self) -> EscalationPolicy:
        """Return the active escalation policy."""
        return self._policy

    def decide(self, result: EvaluationResult) -> EscalationDecision:
        """Determine the escalation tier for the given evaluation result."""
        triggered = result.triggered_rules
        triggered_count = len(triggered)

        if triggered_count == 0:
            return EscalationDecision(
                tier=EscalationTier.LOG,
                reason="No rules triggered",
                triggered_count=0,
                should_notify=False,
                should_pause=False,
                should_block=False,
                should_remediate=False,
            )

        # 1. Highest tier from individual rule actions
        action_tier = EscalationTier.LOG
        for evaluation in triggered:
            action_value: str = evaluation.rule.action.value
            mapped = self._policy.action_tiers.get(action_value, EscalationTier.WARN)
            if mapped > action_tier:
                action_tier = mapped

        # 2. Highest tier from triggered-rule-count thresholds
        count_tier = EscalationTier.LOG
        for threshold in self._policy.count_thresholds:
            if triggered_count >= threshold.min_triggered and threshold.tier > count_tier:
                count_tier = threshold.tier

        tier = EscalationTier(max(action_tier, count_tier))

        reason = self._build_reason(triggered_count, action_tier, count_tier, tier)

        return EscalationDecision(
            tier=tier,
            reason=reason,
            triggered_count=triggered_count,
            should_notify=tier >= EscalationTier.WARN,
            should_pause=tier >= EscalationTier.REQUIRE_APPROVAL,
            should_block=tier >= EscalationTier.BLOCK,
            should_remediate=tier >= EscalationTier.AUTO_REMEDIATE,
        )

    def tier_for_action(self, action: GuardrailAction) -> EscalationTier:
        """Return the escalation tier for a single guardrail action."""
        return self._policy.action_tiers.get(action.value, EscalationTier.WARN)

    @staticmethod
    def _build_reason(
        triggered_count: int,
        action_tier: EscalationTier,
        count_tier: EscalationTier,
        final_tier: EscalationTier,
    ) -> str:
        parts: list[str] = [f"{triggered_count} rule(s) triggered"]
        if action_tier == final_tier and count_tier < final_tier:
            parts.append(f"severity escalated to {final_tier.name} by rule action")
        elif count_tier == final_tier and action_tier < final_tier:
            parts.append(f"severity escalated to {final_tier.name} by rule count")
        elif count_tier == action_tier == final_tier:
            parts.append(f"tier {final_tier.name}")
        else:
            parts.append(f"tier {final_tier.name}")
        return "; ".join(parts)
