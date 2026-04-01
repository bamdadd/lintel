"""Parallel agent execution with shared sandbox and live monitoring (REQ-035)."""

from lintel.domain.parallel.coordinator import AgentCoordinator, AgentRunner, LogSink
from lintel.domain.parallel.types import (
    AgentSession,
    AgentSessionStatus,
    ConflictSeverity,
    FileConflict,
    FileOwnership,
    FileRecord,
    ParallelExecutionPlan,
    ParallelExecutionResult,
    SandboxAllocation,
    SharedWorkspace,
)

__all__ = [
    "AgentCoordinator",
    "AgentRunner",
    "AgentSession",
    "AgentSessionStatus",
    "ConflictSeverity",
    "FileConflict",
    "FileOwnership",
    "FileRecord",
    "LogSink",
    "ParallelExecutionPlan",
    "ParallelExecutionResult",
    "SandboxAllocation",
    "SharedWorkspace",
]
