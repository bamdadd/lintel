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
class SandboxCommandExecuted(EventEnvelope):
    event_type: str = "SandboxCommandExecuted"


@dataclass(frozen=True)
class SandboxFileWritten(EventEnvelope):
    event_type: str = "SandboxFileWritten"


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
class SkillRegistered(EventEnvelope):
    event_type: str = "SkillRegistered"


@dataclass(frozen=True)
class SkillUpdated(EventEnvelope):
    event_type: str = "SkillUpdated"


@dataclass(frozen=True)
class SkillRemoved(EventEnvelope):
    event_type: str = "SkillRemoved"


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


# --- Project Events ---


@dataclass(frozen=True)
class ProjectCreated(EventEnvelope):
    event_type: str = "ProjectCreated"


@dataclass(frozen=True)
class ProjectUpdated(EventEnvelope):
    event_type: str = "ProjectUpdated"


@dataclass(frozen=True)
class ProjectArchived(EventEnvelope):
    event_type: str = "ProjectArchived"


@dataclass(frozen=True)
class ProjectRemoved(EventEnvelope):
    event_type: str = "ProjectRemoved"


# --- Work Item Events ---


@dataclass(frozen=True)
class WorkItemCreated(EventEnvelope):
    event_type: str = "WorkItemCreated"


@dataclass(frozen=True)
class WorkItemUpdated(EventEnvelope):
    event_type: str = "WorkItemUpdated"


@dataclass(frozen=True)
class WorkItemCompleted(EventEnvelope):
    event_type: str = "WorkItemCompleted"


@dataclass(frozen=True)
class WorkItemRemoved(EventEnvelope):
    event_type: str = "WorkItemRemoved"


# --- Pipeline Events ---


@dataclass(frozen=True)
class PipelineRunStarted(EventEnvelope):
    event_type: str = "PipelineRunStarted"


@dataclass(frozen=True)
class PipelineStageCompleted(EventEnvelope):
    event_type: str = "PipelineStageCompleted"


@dataclass(frozen=True)
class PipelineRunCompleted(EventEnvelope):
    event_type: str = "PipelineRunCompleted"


@dataclass(frozen=True)
class PipelineRunFailed(EventEnvelope):
    event_type: str = "PipelineRunFailed"


@dataclass(frozen=True)
class PipelineRunCancelled(EventEnvelope):
    event_type: str = "PipelineRunCancelled"


@dataclass(frozen=True)
class PipelineRunDeleted(EventEnvelope):
    event_type: str = "PipelineRunDeleted"


@dataclass(frozen=True)
class PipelineStageApproved(EventEnvelope):
    event_type: str = "PipelineStageApproved"


@dataclass(frozen=True)
class PipelineStageRejected(EventEnvelope):
    event_type: str = "PipelineStageRejected"


@dataclass(frozen=True)
class PipelineStageRetried(EventEnvelope):
    event_type: str = "PipelineStageRetried"


@dataclass(frozen=True)
class StageReportEdited(EventEnvelope):
    event_type: str = "StageReportEdited"


@dataclass(frozen=True)
class StageReportRegenerated(EventEnvelope):
    event_type: str = "StageReportRegenerated"


# --- Resource Version Events (Concourse-inspired) ---


@dataclass(frozen=True)
class ResourceVersionProduced(EventEnvelope):
    event_type: str = "ResourceVersionProduced"


@dataclass(frozen=True)
class ResourceVersionConsumed(EventEnvelope):
    event_type: str = "ResourceVersionConsumed"


# --- Environment Events ---


@dataclass(frozen=True)
class EnvironmentCreated(EventEnvelope):
    event_type: str = "EnvironmentCreated"


@dataclass(frozen=True)
class EnvironmentUpdated(EventEnvelope):
    event_type: str = "EnvironmentUpdated"


@dataclass(frozen=True)
class EnvironmentRemoved(EventEnvelope):
    event_type: str = "EnvironmentRemoved"


# --- Trigger Events ---


@dataclass(frozen=True)
class TriggerCreated(EventEnvelope):
    event_type: str = "TriggerCreated"


@dataclass(frozen=True)
class TriggerUpdated(EventEnvelope):
    event_type: str = "TriggerUpdated"


@dataclass(frozen=True)
class TriggerRemoved(EventEnvelope):
    event_type: str = "TriggerRemoved"


@dataclass(frozen=True)
class TriggerFired(EventEnvelope):
    event_type: str = "TriggerFired"


# --- Artifact & Test Events ---


@dataclass(frozen=True)
class ArtifactStored(EventEnvelope):
    event_type: str = "ArtifactStored"


@dataclass(frozen=True)
class TestRunCompleted(EventEnvelope):
    event_type: str = "TestRunCompleted"


# --- Approval Events ---


@dataclass(frozen=True)
class ApprovalRequested(EventEnvelope):
    event_type: str = "ApprovalRequested"


@dataclass(frozen=True)
class ApprovalExpired(EventEnvelope):
    event_type: str = "ApprovalExpired"


# --- Notification Events ---


@dataclass(frozen=True)
class NotificationSent(EventEnvelope):
    event_type: str = "NotificationSent"


# --- User & Team Events ---


@dataclass(frozen=True)
class UserCreated(EventEnvelope):
    event_type: str = "UserCreated"


@dataclass(frozen=True)
class UserUpdated(EventEnvelope):
    event_type: str = "UserUpdated"


@dataclass(frozen=True)
class UserRemoved(EventEnvelope):
    event_type: str = "UserRemoved"


@dataclass(frozen=True)
class TeamCreated(EventEnvelope):
    event_type: str = "TeamCreated"


@dataclass(frozen=True)
class TeamUpdated(EventEnvelope):
    event_type: str = "TeamUpdated"


@dataclass(frozen=True)
class TeamRemoved(EventEnvelope):
    event_type: str = "TeamRemoved"


# --- AI Provider & Model Events ---


@dataclass(frozen=True)
class AIProviderCreated(EventEnvelope):
    event_type: str = "AIProviderCreated"


@dataclass(frozen=True)
class AIProviderUpdated(EventEnvelope):
    event_type: str = "AIProviderUpdated"


@dataclass(frozen=True)
class AIProviderRemoved(EventEnvelope):
    event_type: str = "AIProviderRemoved"


@dataclass(frozen=True)
class AIProviderApiKeyUpdated(EventEnvelope):
    event_type: str = "AIProviderApiKeyUpdated"


@dataclass(frozen=True)
class ModelRegistered(EventEnvelope):
    event_type: str = "ModelRegistered"


@dataclass(frozen=True)
class ModelUpdated(EventEnvelope):
    event_type: str = "ModelUpdated"


@dataclass(frozen=True)
class ModelRemoved(EventEnvelope):
    event_type: str = "ModelRemoved"


@dataclass(frozen=True)
class ModelAssignmentCreated(EventEnvelope):
    event_type: str = "ModelAssignmentCreated"


@dataclass(frozen=True)
class ModelAssignmentRemoved(EventEnvelope):
    event_type: str = "ModelAssignmentRemoved"


# --- Variable Events ---


@dataclass(frozen=True)
class VariableCreated(EventEnvelope):
    event_type: str = "VariableCreated"


@dataclass(frozen=True)
class VariableUpdated(EventEnvelope):
    event_type: str = "VariableUpdated"


@dataclass(frozen=True)
class VariableRemoved(EventEnvelope):
    event_type: str = "VariableRemoved"


# --- Workflow Definition Events ---


@dataclass(frozen=True)
class WorkflowDefinitionCreated(EventEnvelope):
    event_type: str = "WorkflowDefinitionCreated"


@dataclass(frozen=True)
class WorkflowDefinitionUpdated(EventEnvelope):
    event_type: str = "WorkflowDefinitionUpdated"


@dataclass(frozen=True)
class WorkflowDefinitionRemoved(EventEnvelope):
    event_type: str = "WorkflowDefinitionRemoved"


# --- Notification Rule Events ---


@dataclass(frozen=True)
class NotificationRuleCreated(EventEnvelope):
    event_type: str = "NotificationRuleCreated"


@dataclass(frozen=True)
class NotificationRuleUpdated(EventEnvelope):
    event_type: str = "NotificationRuleUpdated"


@dataclass(frozen=True)
class NotificationRuleRemoved(EventEnvelope):
    event_type: str = "NotificationRuleRemoved"


# --- MCP Server Events ---


@dataclass(frozen=True)
class MCPServerRegistered(EventEnvelope):
    event_type: str = "MCPServerRegistered"


@dataclass(frozen=True)
class MCPServerUpdated(EventEnvelope):
    event_type: str = "MCPServerUpdated"


@dataclass(frozen=True)
class MCPServerRemoved(EventEnvelope):
    event_type: str = "MCPServerRemoved"


# --- Policy Events ---


@dataclass(frozen=True)
class PolicyCreated(EventEnvelope):
    event_type: str = "PolicyCreated"


@dataclass(frozen=True)
class PolicyUpdated(EventEnvelope):
    event_type: str = "PolicyUpdated"


@dataclass(frozen=True)
class PolicyRemoved(EventEnvelope):
    event_type: str = "PolicyRemoved"


# --- Settings & Connection Events ---


@dataclass(frozen=True)
class ConnectionCreated(EventEnvelope):
    event_type: str = "ConnectionCreated"


@dataclass(frozen=True)
class ConnectionUpdated(EventEnvelope):
    event_type: str = "ConnectionUpdated"


@dataclass(frozen=True)
class ConnectionRemoved(EventEnvelope):
    event_type: str = "ConnectionRemoved"


@dataclass(frozen=True)
class SettingsUpdated(EventEnvelope):
    event_type: str = "SettingsUpdated"


# --- Conversation Events ---


@dataclass(frozen=True)
class ConversationCreated(EventEnvelope):
    event_type: str = "ConversationCreated"


@dataclass(frozen=True)
class ConversationDeleted(EventEnvelope):
    event_type: str = "ConversationDeleted"


@dataclass(frozen=True)
class WorkflowTriggered(EventEnvelope):
    event_type: str = "WorkflowTriggered"


@dataclass(frozen=True)
class ProjectSelected(EventEnvelope):
    event_type: str = "ProjectSelected"


# --- Agent Definition Events ---


@dataclass(frozen=True)
class AgentDefinitionCreated(EventEnvelope):
    event_type: str = "AgentDefinitionCreated"


@dataclass(frozen=True)
class AgentDefinitionUpdated(EventEnvelope):
    event_type: str = "AgentDefinitionUpdated"


@dataclass(frozen=True)
class AgentDefinitionRemoved(EventEnvelope):
    event_type: str = "AgentDefinitionRemoved"


# --- Approval Request Events ---


@dataclass(frozen=True)
class ApprovalRequestCreated(EventEnvelope):
    event_type: str = "ApprovalRequestCreated"


@dataclass(frozen=True)
class ApprovalRequestApproved(EventEnvelope):
    event_type: str = "ApprovalRequestApproved"


@dataclass(frozen=True)
class ApprovalRequestRejected(EventEnvelope):
    event_type: str = "ApprovalRequestRejected"


# --- Audit Events ---


@dataclass(frozen=True)
class AuditRecorded(EventEnvelope):
    event_type: str = "AuditRecorded"


# --- Collaboration Events (Layer 2) ---


@dataclass(frozen=True)
class TeamMemberAdded(EventEnvelope):
    event_type: str = "TeamMemberAdded"


@dataclass(frozen=True)
class TeamMemberRemoved(EventEnvelope):
    event_type: str = "TeamMemberRemoved"


@dataclass(frozen=True)
class TeamMemberRoleChanged(EventEnvelope):
    event_type: str = "TeamMemberRoleChanged"


@dataclass(frozen=True)
class ChannelRegistered(EventEnvelope):
    event_type: str = "ChannelRegistered"


@dataclass(frozen=True)
class ChannelUpdated(EventEnvelope):
    event_type: str = "ChannelUpdated"


@dataclass(frozen=True)
class ChannelDisabled(EventEnvelope):
    event_type: str = "ChannelDisabled"


@dataclass(frozen=True)
class IntegrationRegistered(EventEnvelope):
    event_type: str = "IntegrationRegistered"


@dataclass(frozen=True)
class IntegrationSynced(EventEnvelope):
    event_type: str = "IntegrationSynced"


@dataclass(frozen=True)
class IntegrationFailed(EventEnvelope):
    event_type: str = "IntegrationFailed"


# --- Guardrail Events (Layer 3) ---


@dataclass(frozen=True)
class GuardrailTriggered(EventEnvelope):
    event_type: str = "GuardrailTriggered"


@dataclass(frozen=True)
class GuardrailEscalated(EventEnvelope):
    event_type: str = "GuardrailEscalated"


@dataclass(frozen=True)
class GuardrailResolved(EventEnvelope):
    event_type: str = "GuardrailResolved"


# --- Deployment Events (Layer 4) ---


@dataclass(frozen=True)
class DeploymentStarted(EventEnvelope):
    event_type: str = "DeploymentStarted"


@dataclass(frozen=True)
class DeploymentSucceeded(EventEnvelope):
    event_type: str = "DeploymentSucceeded"


@dataclass(frozen=True)
class DeploymentFailed(EventEnvelope):
    event_type: str = "DeploymentFailed"


@dataclass(frozen=True)
class DeploymentRolledBack(EventEnvelope):
    event_type: str = "DeploymentRolledBack"


@dataclass(frozen=True)
class ExperimentStarted(EventEnvelope):
    event_type: str = "ExperimentStarted"


@dataclass(frozen=True)
class VariantAssigned(EventEnvelope):
    event_type: str = "VariantAssigned"


@dataclass(frozen=True)
class ExperimentCompleted(EventEnvelope):
    event_type: str = "ExperimentCompleted"


# --- Metrics Events (Layer 5) ---


@dataclass(frozen=True)
class DeliveryMetricComputed(EventEnvelope):
    event_type: str = "DeliveryMetricComputed"


@dataclass(frozen=True)
class AgentPerformanceComputed(EventEnvelope):
    event_type: str = "AgentPerformanceComputed"


@dataclass(frozen=True)
class HumanPerformanceComputed(EventEnvelope):
    event_type: str = "HumanPerformanceComputed"


# --- Delivery Loop Events (Layer 6) ---


@dataclass(frozen=True)
class DeliveryLoopStarted(EventEnvelope):
    event_type: str = "DeliveryLoopStarted"


@dataclass(frozen=True)
class DeliveryLoopPhaseTransitioned(EventEnvelope):
    event_type: str = "DeliveryLoopPhaseTransitioned"


@dataclass(frozen=True)
class LearningCaptured(EventEnvelope):
    event_type: str = "LearningCaptured"


@dataclass(frozen=True)
class DeliveryLoopCompleted(EventEnvelope):
    event_type: str = "DeliveryLoopCompleted"


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
        SkillRegistered,
        SkillUpdated,
        SkillRemoved,
        SkillInvoked,
        SkillSucceeded,
        SkillFailed,
        SandboxJobScheduled,
        SandboxCreated,
        SandboxCommandExecuted,
        SandboxFileWritten,
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
        ProjectCreated,
        ProjectUpdated,
        ProjectArchived,
        ProjectRemoved,
        WorkItemCreated,
        WorkItemUpdated,
        WorkItemCompleted,
        WorkItemRemoved,
        PipelineRunStarted,
        PipelineStageCompleted,
        PipelineRunCompleted,
        PipelineRunFailed,
        PipelineRunCancelled,
        PipelineRunDeleted,
        PipelineStageApproved,
        PipelineStageRejected,
        PipelineStageRetried,
        ResourceVersionProduced,
        ResourceVersionConsumed,
        EnvironmentCreated,
        EnvironmentUpdated,
        EnvironmentRemoved,
        TriggerCreated,
        TriggerUpdated,
        TriggerRemoved,
        TriggerFired,
        ArtifactStored,
        TestRunCompleted,
        ApprovalRequested,
        ApprovalExpired,
        NotificationSent,
        UserCreated,
        UserUpdated,
        UserRemoved,
        TeamCreated,
        TeamUpdated,
        TeamRemoved,
        AIProviderCreated,
        AIProviderUpdated,
        AIProviderRemoved,
        AIProviderApiKeyUpdated,
        ModelRegistered,
        ModelUpdated,
        ModelRemoved,
        ModelAssignmentCreated,
        ModelAssignmentRemoved,
        VariableCreated,
        VariableUpdated,
        VariableRemoved,
        WorkflowDefinitionCreated,
        WorkflowDefinitionUpdated,
        WorkflowDefinitionRemoved,
        NotificationRuleCreated,
        NotificationRuleUpdated,
        NotificationRuleRemoved,
        MCPServerRegistered,
        MCPServerUpdated,
        MCPServerRemoved,
        PolicyCreated,
        PolicyUpdated,
        PolicyRemoved,
        ConnectionCreated,
        ConnectionUpdated,
        ConnectionRemoved,
        SettingsUpdated,
        ConversationCreated,
        ConversationDeleted,
        WorkflowTriggered,
        ProjectSelected,
        AgentDefinitionCreated,
        AgentDefinitionUpdated,
        AgentDefinitionRemoved,
        ApprovalRequestCreated,
        ApprovalRequestApproved,
        ApprovalRequestRejected,
        AuditRecorded,
        # Layer 2 — Collaboration
        TeamMemberAdded,
        TeamMemberRemoved,
        TeamMemberRoleChanged,
        ChannelRegistered,
        ChannelUpdated,
        ChannelDisabled,
        IntegrationRegistered,
        IntegrationSynced,
        IntegrationFailed,
        # Layer 3 — Guardrails
        GuardrailTriggered,
        GuardrailEscalated,
        GuardrailResolved,
        # Layer 4 — Deployment
        DeploymentStarted,
        DeploymentSucceeded,
        DeploymentFailed,
        DeploymentRolledBack,
        ExperimentStarted,
        VariantAssigned,
        ExperimentCompleted,
        # Layer 5 — Metrics
        DeliveryMetricComputed,
        AgentPerformanceComputed,
        HumanPerformanceComputed,
        # Layer 6 — Delivery Loop
        DeliveryLoopStarted,
        DeliveryLoopPhaseTransitioned,
        LearningCaptured,
        DeliveryLoopCompleted,
    ]
}


def deserialize_event(event_type: str, data: dict[str, Any]) -> EventEnvelope:
    """Deserialize an event from stored data. Raises KeyError for unknown types."""
    cls = EVENT_TYPE_MAP[event_type]
    return cls(**data)
