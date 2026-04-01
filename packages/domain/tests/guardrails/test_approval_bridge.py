"""Tests for GuardrailApprovalBridge (GRD-6)."""

from __future__ import annotations

from uuid import UUID

import pytest

from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
from lintel.domain.guardrails.approval_bridge import GuardrailApprovalBridge
from lintel.domain.guardrails.escalation import EscalationDecision, EscalationTier
from lintel.domain.types import ApprovalStatus


class FakeEventBus:
    """Minimal EventBus fake that records published events."""

    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)

    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: object,
    ) -> str:
        return "sub-1"

    async def unsubscribe(self, subscription_id: str) -> None:
        pass


def _make_decision(
    tier: EscalationTier = EscalationTier.REQUIRE_APPROVAL,
    *,
    should_pause: bool = True,
) -> EscalationDecision:
    return EscalationDecision(
        tier=tier,
        reason="3 rule(s) triggered; tier REQUIRE_APPROVAL",
        triggered_count=3,
        should_notify=True,
        should_pause=should_pause,
        should_block=tier >= EscalationTier.BLOCK,
        should_remediate=tier >= EscalationTier.AUTO_REMEDIATE,
    )


@pytest.fixture()
def approval_store() -> InMemoryApprovalRequestStore:
    return InMemoryApprovalRequestStore()


@pytest.fixture()
def event_bus() -> FakeEventBus:
    return FakeEventBus()


@pytest.fixture()
def bridge(
    approval_store: InMemoryApprovalRequestStore,
    event_bus: FakeEventBus,
) -> GuardrailApprovalBridge:
    return GuardrailApprovalBridge(approval_store, event_bus)  # type: ignore[arg-type]


async def test_request_approval_creates_approval_record(
    bridge: GuardrailApprovalBridge,
    approval_store: InMemoryApprovalRequestStore,
) -> None:
    decision = _make_decision()
    approval_id = await bridge.request_approval(
        decision=decision,
        run_id="run-1",
        rule_id="rule-1",
        rule_name="Cost warning",
    )

    approval = await approval_store.get(approval_id)
    assert approval is not None
    assert approval.run_id == "run-1"
    assert approval.gate_type == "guardrail_approval"
    assert approval.status == ApprovalStatus.PENDING
    assert approval.requested_by == "guardrail_engine"
    assert "Cost warning" in approval.reason


async def test_request_approval_emits_event(
    bridge: GuardrailApprovalBridge,
    event_bus: FakeEventBus,
) -> None:
    decision = _make_decision()
    approval_id = await bridge.request_approval(
        decision=decision,
        run_id="run-2",
        rule_id="rule-2",
        rule_name="Large diff review",
    )

    assert len(event_bus.events) == 1
    event = event_bus.events[0]
    assert event.event_type == "GuardrailApprovalRequested"  # type: ignore[attr-defined]
    payload = event.payload  # type: ignore[attr-defined]
    assert payload["approval_id"] == approval_id
    assert payload["run_id"] == "run-2"
    assert payload["rule_id"] == "rule-2"
    assert payload["rule_name"] == "Large diff review"
    assert payload["tier"] == "REQUIRE_APPROVAL"
    assert payload["triggered_count"] == 3


async def test_request_approval_returns_valid_uuid(
    bridge: GuardrailApprovalBridge,
) -> None:
    decision = _make_decision()
    approval_id = await bridge.request_approval(
        decision=decision,
        run_id="run-3",
        rule_id="rule-3",
        rule_name="Test rule",
    )
    # Should be a valid UUID string
    UUID(approval_id)


async def test_request_approval_rejects_non_pause_decision(
    bridge: GuardrailApprovalBridge,
) -> None:
    decision = _make_decision(
        tier=EscalationTier.WARN,
        should_pause=False,
    )
    with pytest.raises(ValueError, match="should_pause is False"):
        await bridge.request_approval(
            decision=decision,
            run_id="run-4",
            rule_id="rule-4",
            rule_name="Warn only",
        )


async def test_request_approval_works_for_block_tier(
    bridge: GuardrailApprovalBridge,
    approval_store: InMemoryApprovalRequestStore,
    event_bus: FakeEventBus,
) -> None:
    """BLOCK tier also has should_pause=True, so it should create an approval."""
    decision = _make_decision(tier=EscalationTier.BLOCK)
    approval_id = await bridge.request_approval(
        decision=decision,
        run_id="run-5",
        rule_id="rule-5",
        rule_name="Block rule",
    )

    approval = await approval_store.get(approval_id)
    assert approval is not None
    assert len(event_bus.events) == 1
    assert event_bus.events[0].payload["tier"] == "BLOCK"  # type: ignore[attr-defined]


async def test_multiple_approvals_are_independent(
    bridge: GuardrailApprovalBridge,
    approval_store: InMemoryApprovalRequestStore,
    event_bus: FakeEventBus,
) -> None:
    decision = _make_decision()
    id1 = await bridge.request_approval(
        decision=decision, run_id="run-a", rule_id="r1", rule_name="Rule A"
    )
    id2 = await bridge.request_approval(
        decision=decision, run_id="run-b", rule_id="r2", rule_name="Rule B"
    )

    assert id1 != id2
    assert len(event_bus.events) == 2
    all_approvals = await approval_store.list_all()
    assert len(all_approvals) == 2
