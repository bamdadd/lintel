"""Event-driven approval bridge for guardrail escalations (GRD-6).

When the escalation engine produces a decision with ``should_pause=True``
(i.e. tier >= REQUIRE_APPROVAL), this bridge:

1. Creates a pending :class:`ApprovalRequest` in the approval store.
2. Emits a :class:`GuardrailApprovalRequested` event via the EventBus.

This decouples workflow pausing from the guardrail engine — downstream
subscribers (channel notifiers, approval projections) react to the event
independently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
    from lintel.contracts.protocols import EventBus
    from lintel.domain.guardrails.escalation import EscalationDecision

logger = structlog.get_logger()


class GuardrailApprovalBridge:
    """Bridges guardrail escalation decisions to approval requests and events.

    Usage::

        bridge = GuardrailApprovalBridge(approval_store, event_bus)
        if decision.should_pause:
            await bridge.request_approval(
                decision=decision,
                run_id=pipeline_run_id,
                rule_id=rule_id,
                rule_name=rule_name,
            )
    """

    def __init__(
        self,
        approval_store: InMemoryApprovalRequestStore,
        event_bus: EventBus,
    ) -> None:
        self._store = approval_store
        self._bus = event_bus

    async def request_approval(
        self,
        *,
        decision: EscalationDecision,
        run_id: str,
        rule_id: str,
        rule_name: str,
    ) -> str:
        """Create an approval request and emit ``GuardrailApprovalRequested``.

        Parameters
        ----------
        decision:
            The escalation decision (must have ``should_pause=True``).
        run_id:
            The pipeline run that should be paused.
        rule_id:
            The guardrail rule that triggered escalation.
        rule_name:
            Human-readable name of the triggering rule.

        Returns
        -------
        str
            The ``approval_id`` of the newly created request.

        Raises
        ------
        ValueError
            If the decision does not require approval (``should_pause`` is False).
        """
        if not decision.should_pause:
            msg = f"Cannot request approval for tier {decision.tier.name}: should_pause is False"
            raise ValueError(msg)

        from lintel.domain.types import ApprovalRequest, ApprovalStatus
        from lintel.workflows.events import GuardrailApprovalRequested

        approval_id = str(uuid4())

        approval = ApprovalRequest(
            approval_id=approval_id,
            run_id=run_id,
            gate_type="guardrail_approval",
            status=ApprovalStatus.PENDING,
            requested_by="guardrail_engine",
            reason=f"Guardrail rule '{rule_name}' requires approval "
            f"(tier={decision.tier.name}, {decision.reason})",
        )

        await self._store.add(approval)

        event = GuardrailApprovalRequested(
            payload={
                "approval_id": approval_id,
                "run_id": run_id,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "tier": decision.tier.name,
                "reason": decision.reason,
                "triggered_count": decision.triggered_count,
            },
        )
        await self._bus.publish(event)

        logger.info(
            "guardrail_approval_requested",
            approval_id=approval_id,
            run_id=run_id,
            rule_id=rule_id,
            rule_name=rule_name,
            tier=decision.tier.name,
        )

        return approval_id
