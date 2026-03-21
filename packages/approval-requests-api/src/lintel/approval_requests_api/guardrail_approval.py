"""Guardrail approval request handler (GRD-7).

Creates approval request records when REQUIRE_APPROVAL guardrail rules
are triggered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from lintel.approval_requests_api.store import (
        InMemoryApprovalRequestStore,
    )
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()


class GuardrailApprovalHandler:
    """Creates approval requests for REQUIRE_APPROVAL guardrail triggers."""

    HANDLED_TYPES: frozenset[str] = frozenset({"GuardrailTriggered"})

    def __init__(
        self,
        approval_store: InMemoryApprovalRequestStore,
    ) -> None:
        self._store = approval_store

    async def handle(self, event: EventEnvelope) -> None:
        """Handle a GuardrailTriggered event with REQUIRE_APPROVAL action."""
        payload = event.payload
        action = payload.get("action", "")

        if action != "REQUIRE_APPROVAL":
            return

        from lintel.domain.types import ApprovalRequest, ApprovalStatus

        rule_id = str(payload.get("rule_id", ""))
        rule_name = str(payload.get("rule_name", ""))

        approval = ApprovalRequest(
            approval_id=str(uuid4()),
            resource_type="guardrail_rule",
            resource_id=rule_id,
            requested_by="guardrail_engine",
            status=ApprovalStatus.PENDING,
            reason=f"Guardrail rule '{rule_name}' requires approval",
        )

        await self._store.add(approval)

        logger.info(
            "guardrail_approval_created",
            approval_id=approval.approval_id,
            rule_id=rule_id,
            rule_name=rule_name,
        )
