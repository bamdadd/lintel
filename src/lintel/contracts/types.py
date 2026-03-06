"""Core domain types for Lintel. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType
from uuid import UUID


@dataclass(frozen=True)
class ThreadRef:
    """Canonical identifier for a workflow instance (Slack thread)."""

    workspace_id: str
    channel_id: str
    thread_ts: str

    @property
    def stream_id(self) -> str:
        return f"thread:{self.workspace_id}:{self.channel_id}:{self.thread_ts}"

    def __str__(self) -> str:
        return self.stream_id


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class AgentRole(StrEnum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    PM = "pm"
    DESIGNER = "designer"
    SUMMARIZER = "summarizer"


class WorkflowPhase(StrEnum):
    INGESTING = "ingesting"
    PLANNING = "planning"
    AWAITING_SPEC_APPROVAL = "awaiting_spec_approval"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    MERGING = "merging"
    CLOSED = "closed"


class RepoStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ERROR = "error"


@dataclass(frozen=True)
class Repository:
    """A registered git repository that workflows can operate on."""

    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    status: RepoStatus = RepoStatus.ACTIVE


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


class SkillExecutionMode(StrEnum):
    INLINE = "inline"
    ASYNC_JOB = "async_job"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class ModelPolicy:
    """Policy for model selection per agent role."""

    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass(frozen=True)
class SkillDescriptor:
    """Metadata describing a registered skill."""

    name: str
    version: str
    description: str = ""
    input_schema: dict[str, object] | None = None
    output_schema: dict[str, object] | None = None
    execution_mode: SkillExecutionMode = SkillExecutionMode.INLINE
    allowed_agent_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SkillResult:
    """Result of a skill invocation."""

    success: bool
    output: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for creating a sandbox container."""

    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_quota: int = 50000


@dataclass(frozen=True)
class SandboxJob:
    """A command to execute in a sandbox."""

    command: str
    workdir: str | None = None


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandbox command execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""


CorrelationId = NewType("CorrelationId", UUID)
EventId = NewType("EventId", UUID)
