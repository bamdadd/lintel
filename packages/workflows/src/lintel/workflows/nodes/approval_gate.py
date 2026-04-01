"""ApprovalGateNode — confidence-based approval gate (F017/REQ-017).

If agent output confidence >= project threshold → auto-approve with audit event.
If confidence < threshold → interrupt and request human approval.
On resume: approve continues the graph, reject raises NodeRejectedError,
correction present → emits AgentCorrected event.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

import structlog

from lintel.domain.events import ApprovalAutoApproved
from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.types import InterruptType

logger = structlog.get_logger()

# Node type discriminator for the REQ-020 node registry
NODE_TYPE = "approval_gate"

# Legacy mapping kept for backward compatibility
GATE_TO_NODE: dict[str, str] = {
    "research_approval": "approval_gate_research",
    "spec_approval": "approval_gate_spec",
    "pr_approval": "approval_gate_pr",
}


class NodeRejectedError(Exception):
    """Raised when a human reviewer rejects the approval gate."""

    def __init__(self, approval_id: str, reason: str = "") -> None:
        self.approval_id = approval_id
        self.reason = reason
        super().__init__(f"Approval {approval_id} rejected: {reason}")


class ApprovalGateNode(HumanInterruptNode):
    """Confidence-based approval gate with correction capture.

    Behaviour:
    1. Extract agent_output and confidence from graph state.
    2. Read confidence_threshold from graph config (project settings).
    3. If confidence >= threshold: emit ApprovalAutoApproved, continue.
    4. If confidence < threshold: persist ApprovalRequest, emit event,
       call ``interrupt()`` to pause execution.
    5. On resume: parse decision — approve continues, reject raises
       NodeRejectedError, correction emits AgentCorrected event.
    """

    def __init__(
        self,
        node_name: str = "approval_gate",
        *,
        gate_type: str = "",
        timeout: int = 0,
        on_timeout_action: Literal["auto_proceed", "auto_escalate"] = "auto_escalate",
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_name, channel_config=channel_config)
        self._gate_type = gate_type or node_name
        self._timeout = timeout
        self._on_timeout = on_timeout_action

    @property
    def interrupt_type(self) -> InterruptType:
        return InterruptType.APPROVAL_GATE

    @property
    def timeout_seconds(self) -> int:
        return self._timeout

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return self._on_timeout

    # --- Override __call__ to add confidence threshold logic ---

    async def __call__(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute approval gate with confidence-based auto-approval."""
        config = config or {}
        configurable = config.get("configurable", {})

        # Extract confidence from state
        confidence = float(state.get("confidence", 0.0))
        threshold = float(
            configurable.get(
                "confidence_threshold",
                state.get("confidence_threshold", 0.85),
            )
        )

        run_id = str(configurable.get("run_id", "") or state.get("run_id", ""))

        # Auto-approve if confidence meets threshold
        if confidence >= threshold:
            return await self._auto_approve(
                state,
                config,
                confidence,
                threshold,
                run_id,
            )

        # Below threshold — delegate to base class interrupt lifecycle
        # Store extra context for the resume handler
        state = {**state, "_gate_type": self._gate_type}
        return await super().__call__(state, config)

    async def _auto_approve(
        self,
        state: dict[str, Any],
        config: dict[str, Any],
        confidence: float,
        threshold: float,
        run_id: str,
    ) -> dict[str, Any]:
        """Auto-approve and emit audit event when confidence >= threshold."""
        from lintel.workflows.nodes._stage_tracking import (
            NODE_TO_STAGE,
            StageTracker,
        )

        tracker = StageTracker(config, state)
        stage = NODE_TO_STAGE.get(self.node_name, self.node_name)
        await tracker.mark_running(self.node_name)

        approval_id = str(uuid4())

        logger.info(
            "approval_gate_auto_approved",
            gate_type=self._gate_type,
            confidence=confidence,
            threshold=threshold,
            run_id=run_id,
            approval_id=approval_id,
        )

        # Emit auto-approved event
        configurable = config.get("configurable", {})
        event_store = configurable.get("event_store")
        if event_store is None:
            app_state = configurable.get("app_state")
            if app_state is None and run_id:
                from lintel.workflows.nodes._runtime_registry import (
                    get_app_state,
                )

                app_state = get_app_state(run_id)
            if app_state is not None:
                event_store = getattr(app_state, "event_store", None)

        if event_store is not None:
            event = ApprovalAutoApproved(
                payload={
                    "approval_id": approval_id,
                    "run_id": run_id,
                    "stage": stage,
                    "gate_type": self._gate_type,
                    "confidence": confidence,
                    "threshold": threshold,
                },
            )
            try:
                await event_store.append(
                    stream_id=f"run:{run_id}",
                    events=[event],
                )
            except Exception:
                logger.warning(
                    "auto_approved_event_publish_failed",
                    run_id=run_id,
                )

        # Remove from pending approvals
        existing = list(state.get("pending_approvals", []))
        if self._gate_type in existing:
            existing.remove(self._gate_type)

        await tracker.mark_completed(self.node_name)
        return {
            "pending_approvals": existing,
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": (
                        f"Auto-approved (confidence {confidence:.0%} >= threshold {threshold:.0%})"
                    ),
                }
            ],
        }

    def _build_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build interrupt payload including confidence and gate metadata."""
        payload = super()._build_payload(state)
        payload["gate_type"] = self._gate_type
        payload["confidence"] = state.get("confidence", 0.0)
        payload["threshold"] = state.get("confidence_threshold", 0.85)
        # Include latest agent output for reviewer context
        outputs = state.get("agent_outputs", [])
        if outputs:
            last_output = outputs[-1] if isinstance(outputs, list) else outputs
            payload["agent_output"] = last_output
        return payload

    async def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Handle approval/rejection/correction from human reviewer."""
        if not isinstance(human_input, dict):
            human_input = {"decision": "approve"}

        decision = human_input.get("decision", "approve")
        comment = human_input.get("comment", "")
        correction = human_input.get("correction")
        reasoning = human_input.get("reasoning", "")
        resolved_by = human_input.get("resolved_by", "")

        gate_type = state.get("_gate_type", self._gate_type)

        # Remove from pending approvals
        existing = list(state.get("pending_approvals", []))
        if gate_type in existing:
            existing.remove(gate_type)

        if decision == "reject":
            approval_id = human_input.get("approval_id", "unknown")
            raise NodeRejectedError(approval_id, comment)

        result: dict[str, Any] = {
            "pending_approvals": existing,
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": f"Approved by {resolved_by}: {comment}"
                    if comment
                    else f"Approved by {resolved_by or 'reviewer'}",
                }
            ],
        }

        # Handle correction if provided
        if correction is not None:
            result["agent_outputs"] = [
                {
                    "node": self.node_name,
                    "output": (f"Approved with correction by {resolved_by}: {reasoning}"),
                    "correction": correction,
                }
            ]

        return result
