"""Tests for multi-agent collaboration primitives."""

from __future__ import annotations

import asyncio

import pytest

from lintel.agents.collaboration import (
    CollaborationManager,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    SharedContext,
)
from lintel.agents.types import AgentRole

# ── SharedContext ─────────────────────────────────────────────────────


class TestSharedContext:
    def test_set_and_get(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.set("planner", "files", ["a.py"])
        assert ctx.get("planner", "files") == ["a.py"]

    def test_get_missing_returns_default(self) -> None:
        ctx = SharedContext(run_id="r1")
        assert ctx.get("nope", "key") is None
        assert ctx.get("nope", "key", 42) == 42

    def test_get_namespace(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.set("coder", "diff", "+1")
        ctx.set("coder", "branch", "feat/x")
        ns = ctx.get_namespace("coder")
        assert ns == {"diff": "+1", "branch": "feat/x"}
        # Returned dict is a copy
        ns["diff"] = "changed"
        assert ctx.get("coder", "diff") == "+1"

    def test_namespaces(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.set("a", "k", 1)
        ctx.set("b", "k", 2)
        assert sorted(ctx.namespaces()) == ["a", "b"]

    def test_snapshot(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.set("ns", "k", "v")
        snap = ctx.snapshot()
        assert snap == {"ns": {"k": "v"}}

    def test_merge(self) -> None:
        ctx1 = SharedContext(run_id="r1")
        ctx1.set("a", "x", 1)
        ctx2 = SharedContext(run_id="r1")
        ctx2.set("a", "y", 2)
        ctx2.set("b", "z", 3)
        ctx1.merge(ctx2)
        assert ctx1.get("a", "x") == 1
        assert ctx1.get("a", "y") == 2
        assert ctx1.get("b", "z") == 3

    def test_clear_namespace(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.set("ns", "k", "v")
        ctx.clear_namespace("ns")
        assert ctx.get_namespace("ns") == {}

    def test_clear_namespace_missing_is_noop(self) -> None:
        ctx = SharedContext(run_id="r1")
        ctx.clear_namespace("nonexistent")  # no error


# ── DelegationRequest ────────────────────────────────────────────────


class TestDelegationRequest:
    def test_defaults(self) -> None:
        req = DelegationRequest()
        assert req.status == DelegationStatus.PENDING
        assert req.request_id  # auto-generated
        assert req.from_role == AgentRole.PLANNER
        assert req.to_role == AgentRole.CODER

    def test_custom_fields(self) -> None:
        req = DelegationRequest(
            request_id="abc",
            from_role=AgentRole.REVIEWER,
            to_role=AgentRole.CODER,
            task_description="Fix lint errors",
            payload={"files": ["a.py"]},
            priority=5,
        )
        assert req.request_id == "abc"
        assert req.priority == 5
        assert req.task_description == "Fix lint errors"


# ── CollaborationManager ─────────────────────────────────────────────


class TestCollaborationManager:
    def test_delegate_and_query(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        req = DelegationRequest(
            request_id="d1",
            from_role=AgentRole.PLANNER,
            to_role=AgentRole.CODER,
            task_description="Implement feature",
        )
        returned = mgr.delegate(req)
        assert returned.request_id == "d1"
        assert mgr.get_request("d1").status == DelegationStatus.PENDING

    def test_duplicate_delegation_raises(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        req = DelegationRequest(request_id="d1")
        mgr.delegate(req)
        with pytest.raises(ValueError, match="Duplicate"):
            mgr.delegate(req)

    def test_accept(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))
        mgr.accept("d1")
        assert mgr.get_request("d1").status == DelegationStatus.ACCEPTED

    def test_complete_success(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))
        mgr.complete_delegation(DelegationResult(request_id="d1", success=True, output={"ok": 1}))
        assert mgr.get_request("d1").status == DelegationStatus.COMPLETED
        result = mgr.get_result("d1")
        assert result is not None
        assert result.success is True
        assert result.output == {"ok": 1}

    def test_complete_failure(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))
        mgr.complete_delegation(
            DelegationResult(request_id="d1", success=False, error="boom"),
        )
        assert mgr.get_request("d1").status == DelegationStatus.REJECTED
        result = mgr.get_result("d1")
        assert result is not None
        assert result.error == "boom"

    def test_pending_for_role(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(
            DelegationRequest(request_id="d1", to_role=AgentRole.CODER),
        )
        mgr.delegate(
            DelegationRequest(request_id="d2", to_role=AgentRole.REVIEWER),
        )
        mgr.delegate(
            DelegationRequest(request_id="d3", to_role=AgentRole.CODER),
        )
        pending = mgr.pending_for(AgentRole.CODER)
        assert len(pending) == 2
        assert {r.request_id for r in pending} == {"d1", "d3"}

    def test_all_requests(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))
        mgr.delegate(DelegationRequest(request_id="d2"))
        assert len(mgr.all_requests()) == 2

    def test_get_request_unknown_raises(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        with pytest.raises(KeyError, match="Unknown"):
            mgr.get_request("nope")

    def test_get_result_missing_returns_none(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        assert mgr.get_result("nope") is None

    def test_shared_context_accessible(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.shared_context.set("planner", "plan", {"steps": 3})
        assert mgr.shared_context.get("planner", "plan") == {"steps": 3}

    async def test_wait_for_result(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))

        async def _complete() -> None:
            await asyncio.sleep(0.01)
            mgr.complete_delegation(DelegationResult(request_id="d1", success=True))

        asyncio.get_event_loop().create_task(_complete())
        result = await mgr.wait_for_result("d1", timeout=2.0)
        assert result is not None
        assert result.success is True

    async def test_wait_for_result_timeout(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        mgr.delegate(DelegationRequest(request_id="d1"))
        result = await mgr.wait_for_result("d1", timeout=0.01)
        assert result is None
        assert mgr.get_request("d1").status == DelegationStatus.TIMED_OUT

    async def test_wait_for_unknown_raises(self) -> None:
        mgr = CollaborationManager(run_id="r1")
        with pytest.raises(KeyError, match="Unknown"):
            await mgr.wait_for_result("nope")
