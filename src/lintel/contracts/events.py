"""Immutable event types for Lintel's event-sourced architecture.

Events are past-tense facts. They are never rejected or modified.
Every event carries a schema_version for upcasting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from lintel.contracts.types import ActorType, ThreadRef


@dataclass(frozen=True)
class EventEnvelope:
    """Shared envelope for all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    schema_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = ""
    thread_ref: ThreadRef | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


# --- Channel & Ingestion Events ---


@dataclass(frozen=True)
class ThreadMessageReceived(EventEnvelope):
    event_type: str = "ThreadMessageReceived"


@dataclass(frozen=True)
class PIIDetected(EventEnvelope):
    event_type: str = "PIIDetected"


@dataclass(frozen=True)
class PIIAnonymised(EventEnvelope):
    event_type: str = "PIIAnonymised"


@dataclass(frozen=True)
class PIIResidualRiskBlocked(EventEnvelope):
    event_type: str = "PIIResidualRiskBlocked"


# --- Workflow Events ---


@dataclass(frozen=True)
class IntentRouted(EventEnvelope):
    event_type: str = "IntentRouted"


@dataclass(frozen=True)
class WorkflowStarted(EventEnvelope):
    event_type: str = "WorkflowStarted"


@dataclass(frozen=True)
class WorkflowAdvanced(EventEnvelope):
    event_type: str = "WorkflowAdvanced"


# --- Agent Events ---


@dataclass(frozen=True)
class AgentStepScheduled(EventEnvelope):
    event_type: str = "AgentStepScheduled"


@dataclass(frozen=True)
class AgentStepStarted(EventEnvelope):
    event_type: str = "AgentStepStarted"


@dataclass(frozen=True)
class AgentStepCompleted(EventEnvelope):
    event_type: str = "AgentStepCompleted"


@dataclass(frozen=True)
class ModelSelected(EventEnvelope):
    event_type: str = "ModelSelected"


@dataclass(frozen=True)
class ModelCallCompleted(EventEnvelope):
    event_type: str = "ModelCallCompleted"


# --- Sandbox Events ---


@dataclass(frozen=True)
class SandboxJobScheduled(EventEnvelope):
    event_type: str = "SandboxJobScheduled"


@dataclass(frozen=True)
class SandboxCreated(EventEnvelope):
    event_type: str = "SandboxCreated"


@dataclass(frozen=True)
class SandboxArtifactsCollected(EventEnvelope):
    event_type: str = "SandboxArtifactsCollected"


@dataclass(frozen=True)
class SandboxDestroyed(EventEnvelope):
    event_type: str = "SandboxDestroyed"


# --- Credential Events ---


@dataclass(frozen=True)
class CredentialStored(EventEnvelope):
    event_type: str = "CredentialStored"


@dataclass(frozen=True)
class CredentialRevoked(EventEnvelope):
    event_type: str = "CredentialRevoked"


# --- Repo Events ---


@dataclass(frozen=True)
class RepositoryRegistered(EventEnvelope):
    event_type: str = "RepositoryRegistered"


@dataclass(frozen=True)
class RepositoryUpdated(EventEnvelope):
    event_type: str = "RepositoryUpdated"


@dataclass(frozen=True)
class RepositoryRemoved(EventEnvelope):
    event_type: str = "RepositoryRemoved"


@dataclass(frozen=True)
class RepoCloned(EventEnvelope):
    event_type: str = "RepoCloned"


@dataclass(frozen=True)
class BranchCreated(EventEnvelope):
    event_type: str = "BranchCreated"


@dataclass(frozen=True)
class CommitPushed(EventEnvelope):
    event_type: str = "CommitPushed"


@dataclass(frozen=True)
class PRCreated(EventEnvelope):
    event_type: str = "PRCreated"


@dataclass(frozen=True)
class PRCommentAdded(EventEnvelope):
    event_type: str = "PRCommentAdded"


@dataclass(frozen=True)
class HumanApprovalGranted(EventEnvelope):
    event_type: str = "HumanApprovalGranted"


@dataclass(frozen=True)
class HumanApprovalRejected(EventEnvelope):
    event_type: str = "HumanApprovalRejected"


# --- Skill Events ---


@dataclass(frozen=True)
class SkillInvoked(EventEnvelope):
    event_type: str = "SkillInvoked"


@dataclass(frozen=True)
class SkillSucceeded(EventEnvelope):
    event_type: str = "SkillSucceeded"


@dataclass(frozen=True)
class SkillFailed(EventEnvelope):
    event_type: str = "SkillFailed"


# --- Security Events ---


@dataclass(frozen=True)
class VaultRevealRequested(EventEnvelope):
    event_type: str = "VaultRevealRequested"


@dataclass(frozen=True)
class VaultRevealGranted(EventEnvelope):
    event_type: str = "VaultRevealGranted"


@dataclass(frozen=True)
class PolicyDecisionRecorded(EventEnvelope):
    event_type: str = "PolicyDecisionRecorded"


# --- Event Registry ---

EVENT_TYPE_MAP: dict[str, type[EventEnvelope]] = {
    cls.event_type: cls
    for cls in [
        ThreadMessageReceived,
        PIIDetected,
        PIIAnonymised,
        PIIResidualRiskBlocked,
        IntentRouted,
        WorkflowStarted,
        WorkflowAdvanced,
        AgentStepScheduled,
        AgentStepStarted,
        AgentStepCompleted,
        ModelSelected,
        ModelCallCompleted,
        SkillInvoked,
        SkillSucceeded,
        SkillFailed,
        SandboxJobScheduled,
        SandboxCreated,
        SandboxArtifactsCollected,
        SandboxDestroyed,
        CredentialStored,
        CredentialRevoked,
        RepositoryRegistered,
        RepositoryUpdated,
        RepositoryRemoved,
        RepoCloned,
        BranchCreated,
        CommitPushed,
        PRCreated,
        PRCommentAdded,
        HumanApprovalGranted,
        HumanApprovalRejected,
        VaultRevealRequested,
        VaultRevealGranted,
        PolicyDecisionRecorded,
    ]
}


def deserialize_event(event_type: str, data: dict[str, Any]) -> EventEnvelope:
    """Deserialize an event from stored data. Raises KeyError for unknown types."""
    cls = EVENT_TYPE_MAP[event_type]
    return cls(**data)
