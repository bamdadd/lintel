"""Guardrail evaluation engine (GRD-1).

Subscribes to domain events via the EventBus, evaluates matching guardrail
rules using the generic expression evaluator, respects cooldowns, and emits
GuardrailTriggered events when conditions are met.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog

from lintel.domain.guardrails.escalation import EscalationEngine, EscalationPolicy
from lintel.domain.guardrails.evaluator import evaluate_condition
from lintel.domain.guardrails.models import (
    CooldownState,
    EvaluationResult,
    GuardrailAction,
    RuleEvaluation,
    RuleVerdict,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus
    from lintel.domain.guardrails.models import GuardrailRule
    from lintel.domain.guardrails.repository import RuleRepository

logger = structlog.get_logger()


class GuardrailBlockError(Exception):
    """Raised when a BLOCK guardrail rule is triggered."""

    def __init__(self, rule_id: str, rule_name: str, message: str = "") -> None:
        self.rule_id = rule_id
        self.rule_name = rule_name
        super().__init__(message or f"Guardrail BLOCK: {rule_name}")


class GuardrailEngine:
    """Evaluates guardrail rules against incoming events.

    The engine supports two usage patterns:

    1. **EventBus subscriber** — call :meth:`register` to subscribe, then
       the engine is invoked automatically via :meth:`handle`.
    2. **Direct evaluation** — call :meth:`evaluate` with a list of rules
       and a context dict to get structured :class:`EvaluationResult`.
    """

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "RunCompleted",
            "SandboxCommandFinished",
            "TestResultRecorded",
            "ArtifactCreated",
            "PullRequestCreated",
            "ModelCallCompleted",
        }
    )

    def __init__(
        self,
        rule_repo: RuleRepository,
        event_bus: EventBus | None = None,
        *,
        cooldown: CooldownState | None = None,
        clock: Callable[[], float] | None = None,
        escalation_policy: EscalationPolicy | None = None,
    ) -> None:
        self._rule_repo = rule_repo
        self._event_bus = event_bus
        self._cooldown = cooldown or CooldownState()
        self._clock = clock or time.monotonic
        self._escalation = EscalationEngine(escalation_policy)

    # -----------------------------------------------------------------
    # EventBus integration
    # -----------------------------------------------------------------

    async def register(self, bus: EventBus) -> None:
        """Subscribe to all handled event types on the given bus."""
        self._event_bus = bus
        await bus.subscribe(self.HANDLED_TYPES, self)

    async def handle(self, event: EventEnvelope) -> None:
        """Evaluate all matching rules against an incoming event."""
        rules = await self._rule_repo.list_by_event_type(event.event_type)
        if not rules:
            return

        payload: dict[str, Any] = dict(event.payload)
        result = self.evaluate(rules, payload)

        for evaluation in result.triggered_rules:
            await self._fire(evaluation.rule, event)

    # -----------------------------------------------------------------
    # Direct evaluation API
    # -----------------------------------------------------------------

    def evaluate(
        self,
        rules: list[GuardrailRule],
        context: dict[str, Any],
        *,
        scope_key: str = "",
    ) -> EvaluationResult:
        """Evaluate a list of rules against a context dict.

        Args:
            rules: Rules to evaluate.
            context: The payload / context dict (action type, token count, etc.).
            scope_key: Optional scope for cooldown tracking (e.g. project_id).

        Returns:
            An :class:`EvaluationResult` with per-rule verdicts.
        """
        evaluations: list[RuleEvaluation] = []
        has_block = False
        now = self._clock()

        for rule in rules:
            if not rule.enabled:
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        verdict=RuleVerdict.PASS,
                        triggered=False,
                        message="Rule disabled",
                    )
                )
                continue

            # Cooldown check
            if self._cooldown.in_cooldown(rule.rule_id, rule.cooldown_seconds, now, scope_key):
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        verdict=RuleVerdict.PASS,
                        triggered=False,
                        message="In cooldown",
                    )
                )
                continue

            # Evaluate condition
            try:
                triggered = evaluate_condition(rule.condition, context, threshold=rule.threshold)
            except ValueError as exc:
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        verdict=RuleVerdict.ERROR,
                        triggered=False,
                        message=str(exc),
                    )
                )
                continue

            if not triggered:
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        verdict=RuleVerdict.PASS,
                        triggered=False,
                    )
                )
                continue

            # Triggered — record cooldown and determine verdict
            self._cooldown.record(rule.rule_id, now, scope_key)

            if rule.action == GuardrailAction.BLOCK:
                verdict = RuleVerdict.FAIL
                has_block = True
            elif rule.action == GuardrailAction.WARN:
                verdict = RuleVerdict.WARN
            else:
                # REQUIRE_APPROVAL — treat as FAIL (blocks progression)
                verdict = RuleVerdict.FAIL
                has_block = True

            evaluations.append(
                RuleEvaluation(
                    rule=rule,
                    verdict=verdict,
                    triggered=True,
                    message=f"{rule.action.value}: {rule.name}",
                )
            )

        result = EvaluationResult(
            evaluations=tuple(evaluations),
            passed=not has_block,
        )

        decision = self._escalation.decide(result)

        return EvaluationResult(
            evaluations=result.evaluations,
            passed=result.passed,
            escalation=decision,
        )

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    async def _fire(self, rule: GuardrailRule, event: EventEnvelope) -> None:
        """Emit a GuardrailTriggered event and handle BLOCK actions."""
        from lintel.domain.events import GuardrailTriggered

        triggered_event = GuardrailTriggered(
            payload={
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "action": rule.action.value,
                "event_type": rule.event_type,
                "threshold": rule.threshold,
                "source_event_type": event.event_type,
                "source_payload": dict(event.payload),
            },
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
        )

        if self._event_bus is not None:
            await self._event_bus.publish(triggered_event)

        logger.info(
            "guardrail_triggered",
            rule_id=rule.rule_id,
            rule_name=rule.name,
            action=rule.action.value,
            event_type=event.event_type,
        )

        if rule.action == GuardrailAction.BLOCK:
            raise GuardrailBlockError(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                message=f"Guardrail BLOCK: {rule.name} triggered on {event.event_type}",
            )
