"""Tests for AgentCoordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from lintel.domain.parallel.coordinator import AgentCoordinator
from lintel.domain.parallel.types import (
    AgentSession,
    AgentSessionStatus,
    FileOwnership,
    ParallelExecutionPlan,
    SandboxAllocation,
)


def _session(
    agent_id: str = "agent-1",
    role: str = "coder",
) -> AgentSession:
    return AgentSession(
        agent_id=agent_id,
        role=role,
        sandbox_id="sbx-1",
        log_stream_id=f"log-{agent_id}",
    )


def _plan(
    sessions: tuple[AgentSession, ...] | None = None,
    max_parallel: int = 4,
    timeout: int = 30,
) -> ParallelExecutionPlan:
    return ParallelExecutionPlan(
        plan_id="plan-1",
        run_id="run-1",
        sandbox_allocation=SandboxAllocation(sandbox_id="sbx-1"),
        agent_sessions=sessions or (_session(),),
        max_parallel=max_parallel,
        timeout_seconds=timeout,
    )


class SuccessRunner:
    """Runner that always succeeds."""

    async def run(self, session: AgentSession) -> AgentSession:
        return AgentSession(
            agent_id=session.agent_id,
            role=session.role,
            sandbox_id=session.sandbox_id,
            log_stream_id=session.log_stream_id,
            status=AgentSessionStatus.COMPLETED,
            outputs={"result": "ok"},
        )


class FailRunner:
    """Runner that always fails."""

    async def run(self, session: AgentSession) -> AgentSession:
        msg = "boom"
        raise RuntimeError(msg)


class SlowRunner:
    """Runner that takes a long time."""

    async def run(self, session: AgentSession) -> AgentSession:
        await asyncio.sleep(100)
        return AgentSession(
            agent_id=session.agent_id,
            role=session.role,
            sandbox_id=session.sandbox_id,
            log_stream_id=session.log_stream_id,
            status=AgentSessionStatus.COMPLETED,
        )


@dataclass
class FakeLogSink:
    entries: list[tuple[str, str]] = field(default_factory=list)

    async def append(self, stream_id: str, message: str) -> None:
        self.entries.append((stream_id, message))


class MixedRunner:
    """First agent succeeds, second fails."""

    async def run(self, session: AgentSession) -> AgentSession:
        if session.agent_id == "agent-fail":
            msg = "agent error"
            raise ValueError(msg)
        return AgentSession(
            agent_id=session.agent_id,
            role=session.role,
            sandbox_id=session.sandbox_id,
            log_stream_id=session.log_stream_id,
            status=AgentSessionStatus.COMPLETED,
        )


class TestCoordinatorExecute:
    async def test_all_succeed(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        plan = _plan(sessions=(_session("a1"), _session("a2")))
        result = await coord.execute(plan)
        assert len(result.sessions) == 2
        assert all(s.status == AgentSessionStatus.COMPLETED for s in result.sessions)
        assert result.total_duration_seconds > 0

    async def test_runner_exception_captured(self) -> None:
        coord = AgentCoordinator(runner=FailRunner())
        result = await coord.execute(_plan())
        assert result.sessions[0].status == AgentSessionStatus.FAILED
        assert result.sessions[0].error == "boom"

    async def test_timeout_captured(self) -> None:
        coord = AgentCoordinator(runner=SlowRunner())
        plan = _plan(timeout=0)  # immediate timeout
        result = await coord.execute(plan)
        assert result.sessions[0].status == AgentSessionStatus.FAILED
        assert "Timed out" in (result.sessions[0].error or "")

    async def test_mixed_results(self) -> None:
        coord = AgentCoordinator(runner=MixedRunner())
        plan = _plan(sessions=(_session("agent-ok"), _session("agent-fail")))
        result = await coord.execute(plan)
        statuses = {s.agent_id: s.status for s in result.sessions}
        assert statuses["agent-ok"] == AgentSessionStatus.COMPLETED
        assert statuses["agent-fail"] == AgentSessionStatus.FAILED

    async def test_log_sink_receives_entries(self) -> None:
        sink = FakeLogSink()
        coord = AgentCoordinator(runner=SuccessRunner(), log_sink=sink)
        await coord.execute(_plan(sessions=(_session("a1"),)))
        # Should have at least start + finish messages
        assert len(sink.entries) >= 2
        assert any("Starting" in msg for _, msg in sink.entries)
        assert any("finished" in msg for _, msg in sink.entries)

    async def test_workspace_initialized(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        result = await coord.execute(_plan())
        assert result.workspace is not None
        assert result.workspace.sandbox_id == "sbx-1"


class TestCoordinatorFileTracking:
    async def test_register_file_during_execution(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan())
        coord.register_file("main.py", "agent-1")
        assert coord.workspace is not None
        assert len(coord.workspace.files) == 1

    async def test_conflict_detection_via_coordinator(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan())
        coord.register_file("main.py", "agent-1")
        coord.register_file("main.py", "agent-2")
        assert coord.workspace is not None
        assert coord.workspace.has_conflicts()

    async def test_shared_files_no_conflict(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan())
        coord.register_file("shared.py", "a1", FileOwnership.SHARED)
        coord.register_file("shared.py", "a2", FileOwnership.SHARED)
        assert coord.workspace is not None
        assert not coord.workspace.has_conflicts()


class TestCoordinatorSessionAccess:
    async def test_get_session(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan(sessions=(_session("a1"),)))
        s = coord.get_session("a1")
        assert s is not None
        assert s.status == AgentSessionStatus.COMPLETED

    async def test_get_session_missing(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan())
        assert coord.get_session("nonexistent") is None

    async def test_active_sessions_empty_after_completion(self) -> None:
        coord = AgentCoordinator(runner=SuccessRunner())
        await coord.execute(_plan(sessions=(_session("a1"), _session("a2"))))
        assert len(coord.active_sessions()) == 0
