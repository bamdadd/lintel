"""Approval gate workflow node (REQ-F017).

Confidence-based approval gate that auto-approves when the workflow's
confidence score exceeds a configurable threshold, otherwise interrupts
for human approval via the shared ``HumanInterruptNode`` lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import structlog

if TYPE_CHECKING:
    from langgraph.types import Command

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.types import (
    ApprovalDecision,
    ApprovalGateConfig,
    InterruptType,
)

logger = structlog.get_logger()

# Node type discriminator for the REQ-020 node registry
NODE_TYPE = "approval_gate"

GATE_TO_NODE: dict[str, str] = {
    "research_approval": "approval_gate_research",
    "spec_approval": "approval_gate_spec",
    "pr_approval": "approval_gate_pr",
}


class ApprovalGateNode(HumanInterruptNode):
    """LangGraph node that gates workflow progress on human approval.

    If the state contains a ``confidence`` score above the configured
    threshold, the gate auto-approves without interrupting.  Otherwise
    it pauses for human review using the ``HumanInterruptNode`` lifecycle.
    """

    def __init__(
        self,
        node_name: str = "approval_gate",
        *,
        gate_type: str = "spec_approval",
        gate_config: ApprovalGateConfig | None = None,
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_name, channel_config=channel_config)
        self.gate_type = gate_type
        self.gate_config = gate_config or ApprovalGateConfig()

    # --- HumanInterruptNode abstract interface ---

    @property
    def interrupt_type(self) -> InterruptType:
        return InterruptType.APPROVAL_GATE

    @property
    def timeout_seconds(self) -> int:
        return self.gate_config.timeout_seconds

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return "auto_escalate"

    def _build_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = super()._build_payload(state)
        payload["gate_type"] = self.gate_type
        payload["confidence"] = state.get("confidence", 0.0)
        payload["confidence_threshold"] = self.gate_config.confidence_threshold
        payload["required_approvers"] = self.gate_config.required_approvers
        return payload

    # --- Override __call__ to support auto-approve ---

    async def __call__(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | Command[Any]:
        """Execute the approval gate.

        Auto-approves when confidence exceeds the threshold.
        Otherwise delegates to the ``HumanInterruptNode`` interrupt lifecycle.
        """
        from lintel.workflows.nodes._stage_tracking import StageTracker

        config = config or {}
        tracker = StageTracker(config, state)
        node_name = GATE_TO_NODE.get(self.gate_type, self.node_name)
        await tracker.mark_running(node_name)

        confidence: float = float(state.get("confidence", 0.0))
        existing = list(state.get("pending_approvals", []))

        # Auto-approve path
        if confidence >= self.gate_config.confidence_threshold:
            if self.gate_type in existing:
                existing.remove(self.gate_type)

            logger.info(
                "approval_gate_auto_approved",
                gate_type=self.gate_type,
                confidence=confidence,
                threshold=self.gate_config.confidence_threshold,
            )
            await tracker.append_log(
                node_name,
                f"Auto-approved (confidence {confidence:.2f} "
                f">= threshold {self.gate_config.confidence_threshold:.2f})",
            )
            await tracker.mark_completed(node_name)
            return {
                "pending_approvals": existing,
                "approval_decision": ApprovalDecision(
                    approved=True,
                    approver="auto",
                    feedback=f"Auto-approved at confidence {confidence:.2f}",
                ),
            }

        # Human approval path — delegate to HumanInterruptNode.__call__
        await tracker.append_log(
            node_name,
            f"Confidence {confidence:.2f} below threshold "
            f"{self.gate_config.confidence_threshold:.2f}, requesting human approval",
        )
        # We already marked running above, so call the parent which will
        # mark running again (idempotent via stage tracker) then interrupt.
        result = await super().__call__(state, config)

        # Ensure pending_approvals is updated in result
        if isinstance(result, dict) and "pending_approvals" not in result:
            if self.gate_type in existing:
                existing.remove(self.gate_type)
            result["pending_approvals"] = existing

        return result

    async def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Process the human approval decision."""
        existing = list(state.get("pending_approvals", []))
        if self.gate_type in existing:
            existing.remove(self.gate_type)

        # Parse human input into ApprovalDecision
        if isinstance(human_input, dict):
            decision = ApprovalDecision(
                approved=bool(human_input.get("approved", False)),
                approver=str(human_input.get("approver", "")),
                corrections=str(human_input.get("corrections", "")),
                feedback=str(human_input.get("feedback", "")),
            )
        else:
            # Treat truthy input as approval
            decision = ApprovalDecision(approved=bool(human_input))

        logger.info(
            "approval_gate_human_decision",
            gate_type=self.gate_type,
            approved=decision.approved,
            approver=decision.approver,
        )

        result: dict[str, Any] = {
            "pending_approvals": existing,
            "approval_decision": decision,
            "current_phase": state.get("current_phase", ""),
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": (
                        f"Approved by {decision.approver}"
                        if decision.approved
                        else f"Rejected by {decision.approver}"
                    ),
                }
            ],
        }

        if decision.corrections:
            result["corrections"] = decision.corrections

        return result


# ---------------------------------------------------------------------------
# Legacy function API — kept for backward-compatible imports by
# feature_to_pr.py and builtins.py.
# ---------------------------------------------------------------------------


async def approval_gate(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
    *,
    gate_type: str,
) -> dict[str, Any]:
    """Legacy approval gate that auto-approves immediately.

    This preserves the original ``interrupt_before``-based gate contract:
    the graph pauses *before* this node runs, and this function simply
    records that the approval happened.
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config, state)
    node_name = GATE_TO_NODE.get(gate_type, f"approval_gate_{gate_type}")
    await tracker.mark_running(node_name)

    existing = list(state.get("pending_approvals", []))
    if gate_type in existing:
        existing.remove(gate_type)

    logger.info(
        "approval_gate_approved",
        gate_type=gate_type,
        project_id=state.get("project_id", ""),
    )

    await tracker.mark_completed(node_name)
    return {"pending_approvals": existing}
