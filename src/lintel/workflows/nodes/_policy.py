"""Policy evaluation for approval gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.contracts.types import PolicyAction

if TYPE_CHECKING:
    from lintel.api.routes.policies import InMemoryPolicyStore


async def evaluate_gate_policy(
    policy_store: InMemoryPolicyStore | None,
    project_id: str,
    gate_type: str,
) -> PolicyAction:
    """Check if any policies apply to this gate.

    Project-specific policies take priority over global ones.
    Default: REQUIRE_APPROVAL.
    """
    if policy_store is None:
        return PolicyAction.REQUIRE_APPROVAL

    policies = await policy_store.list_all()

    # Filter by gate_type match
    matching = [p for p in policies if p.event_type == gate_type]
    if not matching:
        return PolicyAction.REQUIRE_APPROVAL

    # Project-specific policies take priority
    project_specific = [p for p in matching if p.project_id == project_id]
    if project_specific:
        return project_specific[0].action

    # Global policies (empty project_id)
    global_policies = [p for p in matching if not p.project_id]
    if global_policies:
        return global_policies[0].action

    return PolicyAction.REQUIRE_APPROVAL
