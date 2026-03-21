"""Guardrail evaluation engine (GRD-7).

Subscribes to domain events via the EventBus, evaluates matching guardrail
rules, and emits GuardrailTriggered events when conditions are met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
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
    """Evaluates guardrail rules against incoming events."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "RunCompleted",
            "SandboxCommandFinished",
            "TestResultRecorded",
            "ArtifactCreated",
            "PullRequestCreated",
        }
    )

    def __init__(
        self,
        rule_repo: RuleRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self._rule_repo = rule_repo
        self._event_bus = event_bus

    async def register(self, bus: EventBus) -> None:
        """Subscribe to all handled event types on the given bus."""
        self._event_bus = bus
        await bus.subscribe(self.HANDLED_TYPES, self)

    async def handle(self, event: EventEnvelope) -> None:
        """Evaluate all matching rules against an incoming event."""
        rules = await self._rule_repo.list_by_event_type(event.event_type)
        if not rules:
            return

        payload = event.payload
        for rule in rules:
            if not rule.enabled:
                continue
            triggered = self._evaluate_condition(rule, payload)
            if triggered:
                await self._fire(rule, event)

    def _evaluate_condition(self, rule: GuardrailRule, payload: dict[str, object]) -> bool:
        """Evaluate a rule's condition against an event payload."""
        condition = rule.condition
        threshold = rule.threshold

        # rework_rate > threshold
        if condition == "rework_rate > threshold" and threshold is not None:
            return float(payload.get("rework_rate", 0)) > threshold

        # run_cost > threshold
        if condition == "run_cost > threshold" and threshold is not None:
            return float(payload.get("run_cost", 0)) > threshold

        # project_daily_cost > threshold
        if condition == "project_daily_cost > threshold" and threshold is not None:
            return float(payload.get("project_daily_cost", 0)) > threshold

        # duration_seconds > threshold
        if condition == "duration_seconds > threshold" and threshold is not None:
            return float(payload.get("duration_seconds", 0)) > threshold

        # verdict == 'failed'
        if condition == "verdict == 'failed'":
            return str(payload.get("verdict", "")).lower() == "failed"

        # lines_changed > threshold
        if condition == "lines_changed > threshold" and threshold is not None:
            return float(payload.get("lines_changed", 0)) > threshold

        # pii_detected == true
        if condition == "pii_detected == true":
            return bool(payload.get("pii_detected", False))

        logger.warning(
            "guardrail_unknown_condition",
            condition=condition,
            rule_id=rule.rule_id,
        )
        return False

    async def _fire(self, rule: GuardrailRule, event: EventEnvelope) -> None:
        """Emit a GuardrailTriggered event and handle BLOCK actions."""
        from lintel.domain.events import GuardrailTriggered
        from lintel.domain.guardrails.models import GuardrailAction

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
                message=(f"Guardrail BLOCK: {rule.name} triggered on {event.event_type}"),
            )
