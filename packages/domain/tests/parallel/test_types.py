"""Tests for parallel execution domain types."""

from __future__ import annotations

from lintel.domain.parallel.types import (
    AgentSession,
    AgentSessionStatus,
    ConflictSeverity,
    FileOwnership,
    ParallelExecutionPlan,
    ParallelExecutionResult,
    SandboxAllocation,
    SharedWorkspace,
)


def _session(
    agent_id: str = "agent-1",
    role: str = "coder",
    status: AgentSessionStatus = AgentSessionStatus.PENDING,
) -> AgentSession:
    return AgentSession(
        agent_id=agent_id,
        role=role,
        sandbox_id="sbx-1",
        log_stream_id=f"log-{agent_id}",
        status=status,
    )


class TestAgentSession:
    def test_defaults(self) -> None:
        s = _session()
        assert s.status == AgentSessionStatus.PENDING
        assert s.started_at is None
        assert s.completed_at is None
        assert s.error is None
        assert s.outputs is None

    def test_frozen(self) -> None:
        s = _session()
        try:
            s.status = AgentSessionStatus.RUNNING  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestSandboxAllocation:
    def test_defaults(self) -> None:
        sa = SandboxAllocation(sandbox_id="sbx-1")
        assert sa.image == "lintel-sandbox:latest"
        assert sa.base_workdir == "/workspace"


class TestParallelExecutionPlan:
    def test_agent_ids(self) -> None:
        plan = ParallelExecutionPlan(
            plan_id="plan-1",
            run_id="run-1",
            sandbox_allocation=SandboxAllocation(sandbox_id="sbx-1"),
            agent_sessions=(_session("a1"), _session("a2")),
        )
        assert plan.agent_ids == ("a1", "a2")

    def test_is_complete_all_terminal(self) -> None:
        plan = ParallelExecutionPlan(
            plan_id="plan-1",
            run_id="run-1",
            sandbox_allocation=SandboxAllocation(sandbox_id="sbx-1"),
            agent_sessions=(
                _session("a1", status=AgentSessionStatus.COMPLETED),
                _session("a2", status=AgentSessionStatus.FAILED),
            ),
        )
        assert plan.is_complete is True

    def test_is_complete_false_when_pending(self) -> None:
        plan = ParallelExecutionPlan(
            plan_id="plan-1",
            run_id="run-1",
            sandbox_allocation=SandboxAllocation(sandbox_id="sbx-1"),
            agent_sessions=(
                _session("a1", status=AgentSessionStatus.COMPLETED),
                _session("a2", status=AgentSessionStatus.PENDING),
            ),
        )
        assert plan.is_complete is False

    def test_has_failures(self) -> None:
        plan = ParallelExecutionPlan(
            plan_id="plan-1",
            run_id="run-1",
            sandbox_allocation=SandboxAllocation(sandbox_id="sbx-1"),
            agent_sessions=(
                _session("a1", status=AgentSessionStatus.COMPLETED),
                _session("a2", status=AgentSessionStatus.FAILED),
            ),
        )
        assert plan.has_failures is True


class TestSharedWorkspace:
    def test_register_file_no_conflict(self) -> None:
        ws = SharedWorkspace(sandbox_id="sbx-1")
        ws2 = ws.register_file("main.py", "agent-1")
        assert len(ws2.files) == 1
        assert not ws2.has_conflicts()

    def test_register_file_detects_conflict(self) -> None:
        ws = SharedWorkspace(sandbox_id="sbx-1")
        ws = ws.register_file("main.py", "agent-1")
        ws = ws.register_file("main.py", "agent-2")
        assert ws.has_conflicts()
        assert len(ws.conflicts) == 1
        assert ws.conflicts[0].severity == ConflictSeverity.ERROR

    def test_shared_ownership_no_conflict(self) -> None:
        ws = SharedWorkspace(sandbox_id="sbx-1")
        ws = ws.register_file("main.py", "agent-1", FileOwnership.SHARED)
        ws = ws.register_file("main.py", "agent-2", FileOwnership.SHARED)
        assert not ws.has_conflicts()

    def test_files_by_agent(self) -> None:
        ws = SharedWorkspace(sandbox_id="sbx-1")
        ws = ws.register_file("a.py", "agent-1")
        ws = ws.register_file("b.py", "agent-2")
        ws = ws.register_file("c.py", "agent-1")
        assert len(ws.files_by_agent("agent-1")) == 2
        assert len(ws.files_by_agent("agent-2")) == 1

    def test_re_register_same_agent_updates(self) -> None:
        ws = SharedWorkspace(sandbox_id="sbx-1")
        ws = ws.register_file("a.py", "agent-1", FileOwnership.EXCLUSIVE)
        ws = ws.register_file("a.py", "agent-1", FileOwnership.SHARED)
        assert len(ws.files_by_agent("agent-1")) == 1
        assert ws.files_by_agent("agent-1")[0].ownership == FileOwnership.SHARED


class TestParallelExecutionResult:
    def test_success_rate(self) -> None:
        result = ParallelExecutionResult(
            plan_id="plan-1",
            sessions=(
                _session("a1", status=AgentSessionStatus.COMPLETED),
                _session("a2", status=AgentSessionStatus.COMPLETED),
                _session("a3", status=AgentSessionStatus.FAILED),
            ),
        )
        assert abs(result.success_rate - 2 / 3) < 0.01

    def test_success_rate_empty(self) -> None:
        result = ParallelExecutionResult(plan_id="plan-1")
        assert result.success_rate == 0.0

    def test_succeeded_and_failed(self) -> None:
        result = ParallelExecutionResult(
            plan_id="plan-1",
            sessions=(
                _session("a1", status=AgentSessionStatus.COMPLETED),
                _session("a2", status=AgentSessionStatus.FAILED),
            ),
        )
        assert len(result.succeeded) == 1
        assert len(result.failed) == 1
