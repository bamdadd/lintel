"""AgentCoordinator: manages parallel agent sessions within a shared sandbox."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Protocol, runtime_checkable

from lintel.domain.parallel.types import (
    AgentSession,
    AgentSessionStatus,
    FileOwnership,
    ParallelExecutionPlan,
    ParallelExecutionResult,
    SharedWorkspace,
)


@runtime_checkable
class AgentRunner(Protocol):
    """Protocol for executing a single agent session."""

    async def run(self, session: AgentSession) -> AgentSession: ...


@runtime_checkable
class LogSink(Protocol):
    """Protocol for appending log entries per agent stream."""

    async def append(self, stream_id: str, message: str) -> None: ...


@dataclass
class AgentCoordinator:
    """Orchestrates parallel agent execution with shared sandbox and monitoring.

    Manages lifecycle of multiple agent sessions: starts them concurrently
    (respecting ``max_parallel``), monitors progress, collects results,
    and tracks file ownership via ``SharedWorkspace``.
    """

    runner: AgentRunner
    log_sink: LogSink | None = None
    _workspace: SharedWorkspace | None = field(default=None, init=False)
    _sessions: dict[str, AgentSession] = field(default_factory=dict, init=False)

    async def _log(self, stream_id: str, message: str) -> None:
        if self.log_sink is not None:
            await self.log_sink.append(stream_id, message)

    async def execute(self, plan: ParallelExecutionPlan) -> ParallelExecutionResult:
        """Run all agent sessions in the plan, respecting max_parallel."""
        self._workspace = SharedWorkspace(sandbox_id=plan.sandbox_allocation.sandbox_id)
        self._sessions = {s.agent_id: s for s in plan.agent_sessions}

        start = time.monotonic()
        semaphore = asyncio.Semaphore(plan.max_parallel)

        async def _run_one(session: AgentSession) -> AgentSession:
            async with semaphore:
                await self._log(session.log_stream_id, f"Starting agent {session.agent_id}")
                self._sessions[session.agent_id] = AgentSession(
                    agent_id=session.agent_id,
                    role=session.role,
                    sandbox_id=session.sandbox_id,
                    log_stream_id=session.log_stream_id,
                    status=AgentSessionStatus.RUNNING,
                )
                try:
                    result = await asyncio.wait_for(
                        self.runner.run(session),
                        timeout=plan.timeout_seconds,
                    )
                except TimeoutError:
                    result = AgentSession(
                        agent_id=session.agent_id,
                        role=session.role,
                        sandbox_id=session.sandbox_id,
                        log_stream_id=session.log_stream_id,
                        status=AgentSessionStatus.FAILED,
                        error="Timed out",
                    )
                except Exception as exc:
                    result = AgentSession(
                        agent_id=session.agent_id,
                        role=session.role,
                        sandbox_id=session.sandbox_id,
                        log_stream_id=session.log_stream_id,
                        status=AgentSessionStatus.FAILED,
                        error=str(exc),
                    )
                self._sessions[session.agent_id] = result
                await self._log(
                    session.log_stream_id,
                    f"Agent {session.agent_id} finished: {result.status}",
                )
                return result

        tasks = [_run_one(s) for s in plan.agent_sessions]
        completed = await asyncio.gather(*tasks, return_exceptions=False)
        elapsed = time.monotonic() - start

        return ParallelExecutionResult(
            plan_id=plan.plan_id,
            sessions=tuple(completed),
            workspace=self._workspace,
            total_duration_seconds=elapsed,
        )

    def register_file(
        self,
        file_path: str,
        agent_id: str,
        ownership: FileOwnership = FileOwnership.EXCLUSIVE,
    ) -> None:
        """Register a file modification during execution."""
        if self._workspace is not None:
            self._workspace = self._workspace.register_file(file_path, agent_id, ownership)

    def get_session(self, agent_id: str) -> AgentSession | None:
        """Get the current state of an agent session."""
        return self._sessions.get(agent_id)

    def active_sessions(self) -> tuple[AgentSession, ...]:
        """Return all currently running sessions."""
        return tuple(s for s in self._sessions.values() if s.status == AgentSessionStatus.RUNNING)

    @property
    def workspace(self) -> SharedWorkspace | None:
        """Current shared workspace state."""
        return self._workspace
