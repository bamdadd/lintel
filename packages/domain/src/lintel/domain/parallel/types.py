"""Domain types for parallel agent execution with shared sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class AgentSessionStatus(StrEnum):
    """Lifecycle status of an individual agent session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileOwnership(StrEnum):
    """How a file is owned within the shared workspace."""

    EXCLUSIVE = "exclusive"
    SHARED = "shared"


class ConflictSeverity(StrEnum):
    """Severity of a file conflict between agents."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class AgentSession:
    """Tracks a single agent's execution within a parallel group."""

    agent_id: str
    role: str
    sandbox_id: str
    log_stream_id: str
    status: AgentSessionStatus = AgentSessionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    outputs: dict[str, object] | None = None


@dataclass(frozen=True)
class SandboxAllocation:
    """Configuration for a shared sandbox used by parallel agents."""

    sandbox_id: str
    image: str = "lintel-sandbox:latest"
    memory_limit: str = "4g"
    cpu_quota: int = 200000
    timeout_seconds: int = 3600
    base_workdir: str = "/workspace"


@dataclass(frozen=True)
class ParallelExecutionPlan:
    """Defines which agents run concurrently in a shared sandbox."""

    plan_id: str
    run_id: str
    sandbox_allocation: SandboxAllocation
    agent_sessions: tuple[AgentSession, ...] = ()
    max_parallel: int = 4
    timeout_seconds: int = 3600

    @property
    def agent_ids(self) -> tuple[str, ...]:
        """Return all agent IDs in this plan."""
        return tuple(s.agent_id for s in self.agent_sessions)

    @property
    def is_complete(self) -> bool:
        """True when all sessions have a terminal status."""
        terminal = {
            AgentSessionStatus.COMPLETED,
            AgentSessionStatus.FAILED,
            AgentSessionStatus.CANCELLED,
        }
        return all(s.status in terminal for s in self.agent_sessions)

    @property
    def has_failures(self) -> bool:
        """True if any session failed."""
        return any(s.status == AgentSessionStatus.FAILED for s in self.agent_sessions)


@dataclass(frozen=True)
class FileConflict:
    """A conflict detected when multiple agents modify the same file."""

    file_path: str
    agent_ids: tuple[str, ...]
    severity: ConflictSeverity = ConflictSeverity.ERROR
    description: str = ""


@dataclass(frozen=True)
class FileRecord:
    """Tracks a file owned or modified by an agent."""

    file_path: str
    agent_id: str
    ownership: FileOwnership = FileOwnership.EXCLUSIVE


@dataclass(frozen=True)
class SharedWorkspace:
    """Tracks file ownership and detects conflicts across agents in a sandbox."""

    sandbox_id: str
    files: tuple[FileRecord, ...] = ()
    conflicts: tuple[FileConflict, ...] = ()

    def register_file(
        self,
        file_path: str,
        agent_id: str,
        ownership: FileOwnership = FileOwnership.EXCLUSIVE,
    ) -> SharedWorkspace:
        """Register a file and return updated workspace, detecting conflicts."""
        new_record = FileRecord(file_path=file_path, agent_id=agent_id, ownership=ownership)
        existing_owners = tuple(
            f.agent_id for f in self.files if f.file_path == file_path and f.agent_id != agent_id
        )
        new_conflicts = self.conflicts
        if existing_owners and ownership == FileOwnership.EXCLUSIVE:
            conflict = FileConflict(
                file_path=file_path,
                agent_ids=(*existing_owners, agent_id),
                severity=ConflictSeverity.ERROR,
                description=(
                    f"File {file_path} modified by agents: "
                    f"{', '.join((*existing_owners, agent_id))}"
                ),
            )
            new_conflicts = (*self.conflicts, conflict)
        # Remove old record for this agent+path, add new one
        kept = tuple(
            f for f in self.files if not (f.file_path == file_path and f.agent_id == agent_id)
        )
        return SharedWorkspace(
            sandbox_id=self.sandbox_id,
            files=(*kept, new_record),
            conflicts=new_conflicts,
        )

    def files_by_agent(self, agent_id: str) -> tuple[FileRecord, ...]:
        """Return all files owned/modified by a specific agent."""
        return tuple(f for f in self.files if f.agent_id == agent_id)

    def has_conflicts(self) -> bool:
        """True if any file conflicts exist."""
        return len(self.conflicts) > 0


@dataclass(frozen=True)
class ParallelExecutionResult:
    """Aggregated result of a parallel execution plan."""

    plan_id: str
    sessions: tuple[AgentSession, ...] = ()
    workspace: SharedWorkspace | None = None
    total_duration_seconds: float = 0.0

    @property
    def succeeded(self) -> tuple[AgentSession, ...]:
        """Sessions that completed successfully."""
        return tuple(s for s in self.sessions if s.status == AgentSessionStatus.COMPLETED)

    @property
    def failed(self) -> tuple[AgentSession, ...]:
        """Sessions that failed."""
        return tuple(s for s in self.sessions if s.status == AgentSessionStatus.FAILED)

    @property
    def success_rate(self) -> float:
        """Fraction of sessions that succeeded (0.0-1.0)."""
        if not self.sessions:
            return 0.0
        return len(self.succeeded) / len(self.sessions)
