"""Command schemas express intent. Commands are imperative and may fail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.contracts.types import AgentRole, RepoStatus, ThreadRef


@dataclass(frozen=True)
class ProcessIncomingMessage:
    thread_ref: ThreadRef
    raw_text: str
    sender_id: str
    sender_name: str
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class StartWorkflow:
    thread_ref: ThreadRef
    workflow_type: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ScheduleAgentStep:
    thread_ref: ThreadRef
    agent_role: AgentRole
    step_name: str
    context: dict[str, object] = field(default_factory=dict)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ScheduleSandboxJob:
    thread_ref: ThreadRef
    agent_role: AgentRole
    repo_url: str
    base_sha: str
    commands: list[str] = field(default_factory=list)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class GrantApproval:
    thread_ref: ThreadRef
    gate_type: str
    approver_id: str
    approver_name: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RejectApproval:
    thread_ref: ThreadRef
    gate_type: str
    rejector_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RegisterRepository:
    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class UpdateRepository:
    repo_id: str
    name: str | None = None
    default_branch: str | None = None
    owner: str | None = None
    status: RepoStatus | None = None
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RemoveRepository:
    repo_id: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RevealPII:
    thread_ref: ThreadRef
    placeholder: str
    requester_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)
