"""Tests for policy evaluation."""

from __future__ import annotations

from lintel.domain.types import Policy, PolicyAction
from lintel.policies_api.store import InMemoryPolicyStore
from lintel.workflows.nodes._policy import evaluate_gate_policy


class TestEvaluateGatePolicy:
    async def test_returns_require_approval_with_no_store(self) -> None:
        result = await evaluate_gate_policy(None, "proj-1", "spec_approval")
        assert result == PolicyAction.REQUIRE_APPROVAL

    async def test_returns_require_approval_with_empty_store(self) -> None:
        store = InMemoryPolicyStore()
        result = await evaluate_gate_policy(store, "proj-1", "spec_approval")
        assert result == PolicyAction.REQUIRE_APPROVAL

    async def test_returns_auto_approve_when_matching(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Auto approve specs",
                event_type="spec_approval",
                action=PolicyAction.AUTO_APPROVE,
                project_id="proj-1",
            )
        )
        result = await evaluate_gate_policy(store, "proj-1", "spec_approval")
        assert result == PolicyAction.AUTO_APPROVE

    async def test_returns_block_when_matching(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Block merges",
                event_type="pr_approval",
                action=PolicyAction.BLOCK,
                project_id="proj-1",
            )
        )
        result = await evaluate_gate_policy(store, "proj-1", "pr_approval")
        assert result == PolicyAction.BLOCK

    async def test_non_matching_gate_type(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Auto approve specs",
                event_type="spec_approval",
                action=PolicyAction.AUTO_APPROVE,
                project_id="proj-1",
            )
        )
        result = await evaluate_gate_policy(
            store,
            "proj-1",
            "pr_approval",
        )
        assert result == PolicyAction.REQUIRE_APPROVAL

    async def test_global_policy_applies(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Global auto approve",
                event_type="spec_approval",
                action=PolicyAction.AUTO_APPROVE,
                project_id="",
            )
        )
        result = await evaluate_gate_policy(store, "proj-1", "spec_approval")
        assert result == PolicyAction.AUTO_APPROVE

    async def test_project_specific_overrides_global(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Global auto",
                event_type="spec_approval",
                action=PolicyAction.AUTO_APPROVE,
                project_id="",
            )
        )
        await store.add(
            Policy(
                policy_id="p2",
                name="Project block",
                event_type="spec_approval",
                action=PolicyAction.BLOCK,
                project_id="proj-1",
            )
        )
        result = await evaluate_gate_policy(store, "proj-1", "spec_approval")
        assert result == PolicyAction.BLOCK

    async def test_non_matching_project_excluded(self) -> None:
        store = InMemoryPolicyStore()
        await store.add(
            Policy(
                policy_id="p1",
                name="Other project",
                event_type="spec_approval",
                action=PolicyAction.AUTO_APPROVE,
                project_id="proj-other",
            )
        )
        result = await evaluate_gate_policy(store, "proj-1", "spec_approval")
        assert result == PolicyAction.REQUIRE_APPROVAL
