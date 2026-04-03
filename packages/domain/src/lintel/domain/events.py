"""Domain events.

Defines all general domain events that don't belong to a specific
infrastructure package. Events for workflows/pipelines live in
lintel.workflows.events; events for agents, sandbox, slack, etc.
live in their respective packages.
"""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events

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


# --- Automation Events ---


@dataclass(frozen=True)
class AutomationCreated(EventEnvelope):
    event_type: str = "AutomationCreated"


@dataclass(frozen=True)
class AutomationUpdated(EventEnvelope):
    event_type: str = "AutomationUpdated"


@dataclass(frozen=True)
class AutomationRemoved(EventEnvelope):
    event_type: str = "AutomationRemoved"


@dataclass(frozen=True)
class AutomationEnabled(EventEnvelope):
    event_type: str = "AutomationEnabled"


@dataclass(frozen=True)
class AutomationDisabled(EventEnvelope):
    event_type: str = "AutomationDisabled"


@dataclass(frozen=True)
class AutomationFired(EventEnvelope):
    event_type: str = "AutomationFired"


@dataclass(frozen=True)
class AutomationSkipped(EventEnvelope):
    event_type: str = "AutomationSkipped"


@dataclass(frozen=True)
class AutomationCancelled(EventEnvelope):
    event_type: str = "AutomationCancelled"


# --- Artifact & Test Events ---


@dataclass(frozen=True)
class ArtifactStored(EventEnvelope):
    event_type: str = "ArtifactStored"


@dataclass(frozen=True)
class TestRunCompleted(EventEnvelope):
    event_type: str = "TestRunCompleted"


# --- Artifact Parsing Events (REQ-010) ---


@dataclass(frozen=True)
class TestResultsParsed(EventEnvelope):
    event_type: str = "TestResultsParsed"


@dataclass(frozen=True)
class CoverageMeasured(EventEnvelope):
    event_type: str = "CoverageMeasured"


@dataclass(frozen=True)
class QualityGateEvaluated(EventEnvelope):
    event_type: str = "QualityGateEvaluated"


# --- Approval Events ---


@dataclass(frozen=True)
class ApprovalRequested(EventEnvelope):
    event_type: str = "ApprovalRequested"


@dataclass(frozen=True)
class ApprovalExpired(EventEnvelope):
    event_type: str = "ApprovalExpired"


@dataclass(frozen=True)
class ApprovalRequestCreated(EventEnvelope):
    event_type: str = "ApprovalRequestCreated"


@dataclass(frozen=True)
class ApprovalRequestApproved(EventEnvelope):
    event_type: str = "ApprovalRequestApproved"


@dataclass(frozen=True)
class ApprovalRequestRejected(EventEnvelope):
    event_type: str = "ApprovalRequestRejected"


# --- Notification Events ---


@dataclass(frozen=True)
class NotificationSent(EventEnvelope):
    event_type: str = "NotificationSent"


@dataclass(frozen=True)
class NotificationRuleCreated(EventEnvelope):
    event_type: str = "NotificationRuleCreated"


@dataclass(frozen=True)
class NotificationRuleUpdated(EventEnvelope):
    event_type: str = "NotificationRuleUpdated"


@dataclass(frozen=True)
class NotificationRuleRemoved(EventEnvelope):
    event_type: str = "NotificationRuleRemoved"


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


@dataclass(frozen=True)
class TeamMemberAdded(EventEnvelope):
    event_type: str = "TeamMemberAdded"


@dataclass(frozen=True)
class TeamMemberRemoved(EventEnvelope):
    event_type: str = "TeamMemberRemoved"


@dataclass(frozen=True)
class TeamMemberRoleChanged(EventEnvelope):
    event_type: str = "TeamMemberRoleChanged"


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


# --- Policy Events ---


@dataclass(frozen=True)
class PolicyDecisionRecorded(EventEnvelope):
    event_type: str = "PolicyDecisionRecorded"


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


# --- Board & Tag Events ---


@dataclass(frozen=True)
class BoardCreated(EventEnvelope):
    event_type: str = "BoardCreated"


@dataclass(frozen=True)
class BoardUpdated(EventEnvelope):
    event_type: str = "BoardUpdated"


@dataclass(frozen=True)
class BoardRemoved(EventEnvelope):
    event_type: str = "BoardRemoved"


@dataclass(frozen=True)
class TagCreated(EventEnvelope):
    event_type: str = "TagCreated"


@dataclass(frozen=True)
class TagUpdated(EventEnvelope):
    event_type: str = "TagUpdated"


@dataclass(frozen=True)
class TagRemoved(EventEnvelope):
    event_type: str = "TagRemoved"


# --- Conversation Events ---


@dataclass(frozen=True)
class ConversationCreated(EventEnvelope):
    event_type: str = "ConversationCreated"


@dataclass(frozen=True)
class ConversationDeleted(EventEnvelope):
    event_type: str = "ConversationDeleted"


@dataclass(frozen=True)
class ProjectSelected(EventEnvelope):
    event_type: str = "ProjectSelected"


# --- Collaboration Events ---


@dataclass(frozen=True)
class ChannelCreated(EventEnvelope):
    """A new channel was created within a team."""

    event_type: str = "ChannelCreated"


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
class ChannelMessagePosted(EventEnvelope):
    """A message was posted to a collaboration channel."""

    event_type: str = "ChannelMessagePosted"


@dataclass(frozen=True)
class IntegrationRegistered(EventEnvelope):
    event_type: str = "IntegrationRegistered"


@dataclass(frozen=True)
class IntegrationSynced(EventEnvelope):
    event_type: str = "IntegrationSynced"


@dataclass(frozen=True)
class IntegrationFailed(EventEnvelope):
    event_type: str = "IntegrationFailed"


# --- Guardrail Events ---


@dataclass(frozen=True)
class GuardrailTriggered(EventEnvelope):
    event_type: str = "GuardrailTriggered"


@dataclass(frozen=True)
class GuardrailEscalated(EventEnvelope):
    event_type: str = "GuardrailEscalated"


@dataclass(frozen=True)
class GuardrailResolved(EventEnvelope):
    event_type: str = "GuardrailResolved"


# --- Deployment Events ---


@dataclass(frozen=True)
class DeploymentStarted(EventEnvelope):
    event_type: str = "DeploymentStarted"


@dataclass(frozen=True)
class DeploymentCompleted(EventEnvelope):
    """A deployment finished (success or failure details in payload)."""

    event_type: str = "DeploymentCompleted"


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
class ExperimentConcluded(EventEnvelope):
    """An experiment was concluded with a winning variant determined."""

    event_type: str = "ExperimentConcluded"


@dataclass(frozen=True)
class ExperimentCompleted(EventEnvelope):
    event_type: str = "ExperimentCompleted"


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


@dataclass(frozen=True)
class MCPToolRegistered(EventEnvelope):
    event_type: str = "MCPToolRegistered"


@dataclass(frozen=True)
class MCPToolRemoved(EventEnvelope):
    event_type: str = "MCPToolRemoved"


@dataclass(frozen=True)
class MCPToolAllowlistUpdated(EventEnvelope):
    event_type: str = "MCPToolAllowlistUpdated"


# --- Compliance Governance Events ---


@dataclass(frozen=True)
class RegulationCreated(EventEnvelope):
    event_type: str = "RegulationCreated"


@dataclass(frozen=True)
class RegulationUpdated(EventEnvelope):
    event_type: str = "RegulationUpdated"


@dataclass(frozen=True)
class RegulationRemoved(EventEnvelope):
    event_type: str = "RegulationRemoved"


@dataclass(frozen=True)
class CompliancePolicyCreated(EventEnvelope):
    event_type: str = "CompliancePolicyCreated"


@dataclass(frozen=True)
class CompliancePolicyUpdated(EventEnvelope):
    event_type: str = "CompliancePolicyUpdated"


@dataclass(frozen=True)
class CompliancePolicyRemoved(EventEnvelope):
    event_type: str = "CompliancePolicyRemoved"


@dataclass(frozen=True)
class ProcedureCreated(EventEnvelope):
    event_type: str = "ProcedureCreated"


@dataclass(frozen=True)
class ProcedureUpdated(EventEnvelope):
    event_type: str = "ProcedureUpdated"


@dataclass(frozen=True)
class ProcedureRemoved(EventEnvelope):
    event_type: str = "ProcedureRemoved"


@dataclass(frozen=True)
class PracticeCreated(EventEnvelope):
    event_type: str = "PracticeCreated"


@dataclass(frozen=True)
class PracticeUpdated(EventEnvelope):
    event_type: str = "PracticeUpdated"


@dataclass(frozen=True)
class PracticeRemoved(EventEnvelope):
    event_type: str = "PracticeRemoved"


@dataclass(frozen=True)
class StrategyCreated(EventEnvelope):
    event_type: str = "StrategyCreated"


@dataclass(frozen=True)
class StrategyUpdated(EventEnvelope):
    event_type: str = "StrategyUpdated"


@dataclass(frozen=True)
class StrategyRemoved(EventEnvelope):
    event_type: str = "StrategyRemoved"


@dataclass(frozen=True)
class KPICreated(EventEnvelope):
    event_type: str = "KPICreated"


@dataclass(frozen=True)
class KPIUpdated(EventEnvelope):
    event_type: str = "KPIUpdated"


@dataclass(frozen=True)
class KPIRemoved(EventEnvelope):
    event_type: str = "KPIRemoved"


@dataclass(frozen=True)
class ComplianceExperimentCreated(EventEnvelope):
    event_type: str = "ComplianceExperimentCreated"


@dataclass(frozen=True)
class ComplianceExperimentUpdated(EventEnvelope):
    event_type: str = "ComplianceExperimentUpdated"


@dataclass(frozen=True)
class ComplianceExperimentRemoved(EventEnvelope):
    event_type: str = "ComplianceExperimentRemoved"


@dataclass(frozen=True)
class ComplianceMetricCreated(EventEnvelope):
    event_type: str = "ComplianceMetricCreated"


@dataclass(frozen=True)
class ComplianceMetricUpdated(EventEnvelope):
    event_type: str = "ComplianceMetricUpdated"


@dataclass(frozen=True)
class ComplianceMetricRemoved(EventEnvelope):
    event_type: str = "ComplianceMetricRemoved"


@dataclass(frozen=True)
class RunMetricRecorded(EventEnvelope):
    event_type: str = "RunMetricRecorded"


@dataclass(frozen=True)
class StrategyMutationSuggested(EventEnvelope):
    event_type: str = "StrategyMutationSuggested"


@dataclass(frozen=True)
class TournamentCompleted(EventEnvelope):
    event_type: str = "TournamentCompleted"


@dataclass(frozen=True)
class KnowledgeEntryCreated(EventEnvelope):
    event_type: str = "KnowledgeEntryCreated"


@dataclass(frozen=True)
class KnowledgeEntryUpdated(EventEnvelope):
    event_type: str = "KnowledgeEntryUpdated"


@dataclass(frozen=True)
class KnowledgeEntryRemoved(EventEnvelope):
    event_type: str = "KnowledgeEntryRemoved"


@dataclass(frozen=True)
class KnowledgeExtractionStarted(EventEnvelope):
    event_type: str = "KnowledgeExtractionStarted"


@dataclass(frozen=True)
class KnowledgeExtractionCompleted(EventEnvelope):
    event_type: str = "KnowledgeExtractionCompleted"


@dataclass(frozen=True)
class KnowledgeExtractionFailed(EventEnvelope):
    event_type: str = "KnowledgeExtractionFailed"


@dataclass(frozen=True)
class ArchitectureDecisionCreated(EventEnvelope):
    event_type: str = "ArchitectureDecisionCreated"


@dataclass(frozen=True)
class ArchitectureDecisionUpdated(EventEnvelope):
    event_type: str = "ArchitectureDecisionUpdated"


@dataclass(frozen=True)
class ArchitectureDecisionRemoved(EventEnvelope):
    event_type: str = "ArchitectureDecisionRemoved"


# --- Google Drive Import Events ---


@dataclass(frozen=True)
class PolicyImportedFromGDrive(EventEnvelope):
    event_type: str = "PolicyImportedFromGDrive"


# --- Policy Generation Events ---


@dataclass(frozen=True)
class PolicyGenerationStarted(EventEnvelope):
    event_type: str = "PolicyGenerationStarted"


@dataclass(frozen=True)
class PolicyGenerationCompleted(EventEnvelope):
    event_type: str = "PolicyGenerationCompleted"


@dataclass(frozen=True)
class PolicyGenerationFailed(EventEnvelope):
    event_type: str = "PolicyGenerationFailed"


# --- Drift Detection Events ---


@dataclass(frozen=True)
class DriftDetected(EventEnvelope):
    event_type: str = "DriftDetected"


@dataclass(frozen=True)
class DriftResolved(EventEnvelope):
    event_type: str = "DriftResolved"


@dataclass(frozen=True)
class DriftEscalated(EventEnvelope):
    event_type: str = "DriftEscalated"


@dataclass(frozen=True)
class DriftRuleCreated(EventEnvelope):
    event_type: str = "DriftRuleCreated"


@dataclass(frozen=True)
class DriftRuleUpdated(EventEnvelope):
    event_type: str = "DriftRuleUpdated"


@dataclass(frozen=True)
class DriftRuleRemoved(EventEnvelope):
    event_type: str = "DriftRuleRemoved"


@dataclass(frozen=True)
class DriftScanStarted(EventEnvelope):
    event_type: str = "DriftScanStarted"


@dataclass(frozen=True)
class DriftScanCompleted(EventEnvelope):
    event_type: str = "DriftScanCompleted"


# --- Context Attachment Events (REQ-027) ---


@dataclass(frozen=True)
class AttachmentUploaded(EventEnvelope):
    event_type: str = "AttachmentUploaded"


@dataclass(frozen=True)
class AttachmentLinked(EventEnvelope):
    event_type: str = "AttachmentLinked"


@dataclass(frozen=True)
class AttachmentRemoved(EventEnvelope):
    event_type: str = "AttachmentRemoved"


# --- Human Approval Events ---


@dataclass(frozen=True)
class HumanApprovalGranted(EventEnvelope):
    event_type: str = "HumanApprovalGranted"


@dataclass(frozen=True)
class HumanApprovalRejected(EventEnvelope):
    event_type: str = "HumanApprovalRejected"


# --- Resource Version Events ---


@dataclass(frozen=True)
class ResourceVersionProduced(EventEnvelope):
    event_type: str = "ResourceVersionProduced"


@dataclass(frozen=True)
class ResourceVersionConsumed(EventEnvelope):
    event_type: str = "ResourceVersionConsumed"


# --- Delivery Loop Events ---


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
class DeliveryLoopAborted(EventEnvelope):
    """A delivery loop iteration was aborted before completion."""

    event_type: str = "DeliveryLoopAborted"


@dataclass(frozen=True)
class DeliveryCheckpointReached(EventEnvelope):
    """A checkpoint was reached during a delivery loop iteration."""

    event_type: str = "DeliveryCheckpointReached"


@dataclass(frozen=True)
class DeliveryLoopCompleted(EventEnvelope):
    event_type: str = "DeliveryLoopCompleted"


# --- Workflow Hook Events ---


@dataclass(frozen=True)
class HookTriggered(EventEnvelope):
    event_type: str = "HookTriggered"


@dataclass(frozen=True)
class HookExecutionFailed(EventEnvelope):
    event_type: str = "HookExecutionFailed"


@dataclass(frozen=True)
class HookLoopDetected(EventEnvelope):
    event_type: str = "HookLoopDetected"


@dataclass(frozen=True)
class PreHookBlocked(EventEnvelope):
    """A pre-hook denied the event from proceeding."""

    event_type: str = "PreHookBlocked"


@dataclass(frozen=True)
class PreHookAllowed(EventEnvelope):
    """All pre-hooks allowed the event to proceed."""

    event_type: str = "PreHookAllowed"


# --- Feedback Ingestion Events (REQ-025) ---


@dataclass(frozen=True)
class FeedbackReceived(EventEnvelope):
    event_type: str = "FeedbackReceived"


@dataclass(frozen=True)
class FeedbackCategorized(EventEnvelope):
    event_type: str = "FeedbackCategorized"


@dataclass(frozen=True)
class FeedbackWorkItemCreated(EventEnvelope):
    event_type: str = "FeedbackWorkItemCreated"


# --- Coding Rules Events ---


@dataclass(frozen=True)
class CodingRuleCreated(EventEnvelope):
    event_type: str = "CodingRuleCreated"


@dataclass(frozen=True)
class CodingRuleUpdated(EventEnvelope):
    event_type: str = "CodingRuleUpdated"


@dataclass(frozen=True)
class CodingRuleRemoved(EventEnvelope):
    event_type: str = "CodingRuleRemoved"


@dataclass(frozen=True)
class RuleViolationDetected(EventEnvelope):
    event_type: str = "RuleViolationDetected"


@dataclass(frozen=True)
class RuleViolationResolved(EventEnvelope):
    event_type: str = "RuleViolationResolved"


# --- AI Firewall Events (REQ-025) ---


@dataclass(frozen=True)
class FirewallRuleCreated(EventEnvelope):
    event_type: str = "FirewallRuleCreated"


@dataclass(frozen=True)
class FirewallRuleUpdated(EventEnvelope):
    event_type: str = "FirewallRuleUpdated"


@dataclass(frozen=True)
class FirewallRuleRemoved(EventEnvelope):
    event_type: str = "FirewallRuleRemoved"


@dataclass(frozen=True)
class AgentRequestBlocked(EventEnvelope):
    event_type: str = "AgentRequestBlocked"


@dataclass(frozen=True)
class AgentRequestAllowed(EventEnvelope):
    event_type: str = "AgentRequestAllowed"


# --- Agent Trust Score Events (REQ-F029) ---


@dataclass(frozen=True)
class TrustScoreCreated(EventEnvelope):
    event_type: str = "TrustScoreCreated"


@dataclass(frozen=True)
class TrustScoreAdjusted(EventEnvelope):
    event_type: str = "TrustScoreAdjusted"


@dataclass(frozen=True)
class TrustScoreRemoved(EventEnvelope):
    event_type: str = "TrustScoreRemoved"


# --- Codebase Index Events (REQ-026) ---


@dataclass(frozen=True)
class CodebaseConnected(EventEnvelope):
    event_type: str = "CodebaseConnected"


@dataclass(frozen=True)
class CodebaseIndexed(EventEnvelope):
    event_type: str = "CodebaseIndexed"


@dataclass(frozen=True)
class CodebaseReindexed(EventEnvelope):
    event_type: str = "CodebaseReindexed"


# --- Agent Action Governance Events (REQ-030) ---


@dataclass(frozen=True)
class GovernancePolicyCreated(EventEnvelope):
    event_type: str = "GovernancePolicyCreated"


@dataclass(frozen=True)
class GovernancePolicyUpdated(EventEnvelope):
    event_type: str = "GovernancePolicyUpdated"


@dataclass(frozen=True)
class GovernancePolicyRemoved(EventEnvelope):
    event_type: str = "GovernancePolicyRemoved"


@dataclass(frozen=True)
class AgentActionAllowed(EventEnvelope):
    event_type: str = "AgentActionAllowed"


@dataclass(frozen=True)
class AgentActionDenied(EventEnvelope):
    event_type: str = "AgentActionDenied"


@dataclass(frozen=True)
class AgentActionApprovalRequested(EventEnvelope):
    event_type: str = "AgentActionApprovalRequested"


# --- Privacy Controls Events (REQ-008) ---


@dataclass(frozen=True)
class MetricVisibilitySet(EventEnvelope):
    event_type: str = "MetricVisibilitySet"


@dataclass(frozen=True)
class MetricVisibilityRemoved(EventEnvelope):
    event_type: str = "MetricVisibilityRemoved"


@dataclass(frozen=True)
class PrivacyPreferenceUpdated(EventEnvelope):
    event_type: str = "PrivacyPreferenceUpdated"


# --- Composable Agent Skills Events (REQ-F033) ---


@dataclass(frozen=True)
class AgentSkillCreated(EventEnvelope):
    event_type: str = "AgentSkillCreated"


@dataclass(frozen=True)
class AgentSkillUpdated(EventEnvelope):
    event_type: str = "AgentSkillUpdated"


@dataclass(frozen=True)
class AgentSkillRemoved(EventEnvelope):
    event_type: str = "AgentSkillRemoved"


@dataclass(frozen=True)
class AgentSkillBound(EventEnvelope):
    event_type: str = "AgentSkillBound"


@dataclass(frozen=True)
class AgentSkillUnbound(EventEnvelope):
    event_type: str = "AgentSkillUnbound"


# --- Slack Notification Events ---


@dataclass(frozen=True)
class SlackNotificationSent(EventEnvelope):
    event_type: str = "SlackNotificationSent"


@dataclass(frozen=True)
class SlackNotificationFailed(EventEnvelope):
    event_type: str = "SlackNotificationFailed"


@dataclass(frozen=True)
class SlackNotificationTemplateCreated(EventEnvelope):
    event_type: str = "SlackNotificationTemplateCreated"


@dataclass(frozen=True)
class SlackNotificationTemplateUpdated(EventEnvelope):
    event_type: str = "SlackNotificationTemplateUpdated"


# --- Workflow Blueprint Events ---


@dataclass(frozen=True)
class WorkflowBlueprintCreated(EventEnvelope):
    event_type: str = "WorkflowBlueprintCreated"


@dataclass(frozen=True)
class WorkflowBlueprintUpdated(EventEnvelope):
    event_type: str = "WorkflowBlueprintUpdated"


@dataclass(frozen=True)
class WorkflowBlueprintRemoved(EventEnvelope):
    event_type: str = "WorkflowBlueprintRemoved"


@dataclass(frozen=True)
class WorkflowBlueprintActivated(EventEnvelope):
    event_type: str = "WorkflowBlueprintActivated"


@dataclass(frozen=True)
class WorkflowBlueprintDeactivated(EventEnvelope):
    event_type: str = "WorkflowBlueprintDeactivated"


# --- Slack Invocation Events ---


@dataclass(frozen=True)
class SlackInvocationReceived(EventEnvelope):
    event_type: str = "SlackInvocationReceived"


@dataclass(frozen=True)
class SlackWorkflowDispatched(EventEnvelope):
    event_type: str = "SlackWorkflowDispatched"


@dataclass(frozen=True)
class SlackWorkflowCompleted(EventEnvelope):
    event_type: str = "SlackWorkflowCompleted"


# --- Sandbox Pool Events ---


@dataclass(frozen=True)
class SandboxImageBuilt(EventEnvelope):
    event_type: str = "SandboxImageBuilt"


@dataclass(frozen=True)
class SandboxImageExpired(EventEnvelope):
    event_type: str = "SandboxImageExpired"


@dataclass(frozen=True)
class PooledSandboxWarmed(EventEnvelope):
    event_type: str = "PooledSandboxWarmed"


@dataclass(frozen=True)
class PooledSandboxAssigned(EventEnvelope):
    event_type: str = "PooledSandboxAssigned"


@dataclass(frozen=True)
class PooledSandboxReleased(EventEnvelope):
    event_type: str = "PooledSandboxReleased"


@dataclass(frozen=True)
class SandboxImageRebuildStarted(EventEnvelope):
    event_type: str = "SandboxImageRebuildStarted"


@dataclass(frozen=True)
class SandboxImageRebuildCompleted(EventEnvelope):
    event_type: str = "SandboxImageRebuildCompleted"


@dataclass(frozen=True)
class SandboxImageRebuildFailed(EventEnvelope):
    event_type: str = "SandboxImageRebuildFailed"


@dataclass(frozen=True)
class SandboxSnapshotCreated(EventEnvelope):
    event_type: str = "SandboxSnapshotCreated"


@dataclass(frozen=True)
class SandboxSnapshotRestored(EventEnvelope):
    event_type: str = "SandboxSnapshotRestored"


@dataclass(frozen=True)
class SandboxSnapshotExpired(EventEnvelope):
    event_type: str = "SandboxSnapshotExpired"


register_events(
    ProjectCreated,
    ProjectUpdated,
    ProjectArchived,
    ProjectRemoved,
    WorkItemCreated,
    WorkItemUpdated,
    WorkItemCompleted,
    WorkItemRemoved,
    EnvironmentCreated,
    EnvironmentUpdated,
    EnvironmentRemoved,
    TriggerCreated,
    TriggerUpdated,
    TriggerRemoved,
    TriggerFired,
    AutomationCreated,
    AutomationUpdated,
    AutomationRemoved,
    AutomationEnabled,
    AutomationDisabled,
    AutomationFired,
    AutomationSkipped,
    AutomationCancelled,
    ArtifactStored,
    TestRunCompleted,
    TestResultsParsed,
    CoverageMeasured,
    QualityGateEvaluated,
    ApprovalRequested,
    ApprovalExpired,
    ApprovalRequestCreated,
    ApprovalRequestApproved,
    ApprovalRequestRejected,
    NotificationSent,
    NotificationRuleCreated,
    NotificationRuleUpdated,
    NotificationRuleRemoved,
    UserCreated,
    UserUpdated,
    UserRemoved,
    TeamCreated,
    TeamUpdated,
    TeamRemoved,
    TeamMemberAdded,
    TeamMemberRemoved,
    TeamMemberRoleChanged,
    VariableCreated,
    VariableUpdated,
    VariableRemoved,
    PolicyDecisionRecorded,
    PolicyCreated,
    PolicyUpdated,
    PolicyRemoved,
    ConnectionCreated,
    ConnectionUpdated,
    ConnectionRemoved,
    SettingsUpdated,
    BoardCreated,
    BoardUpdated,
    BoardRemoved,
    TagCreated,
    TagUpdated,
    TagRemoved,
    ConversationCreated,
    ConversationDeleted,
    ProjectSelected,
    ChannelCreated,
    ChannelRegistered,
    ChannelUpdated,
    ChannelDisabled,
    ChannelMessagePosted,
    IntegrationRegistered,
    IntegrationSynced,
    IntegrationFailed,
    GuardrailTriggered,
    GuardrailEscalated,
    GuardrailResolved,
    DeploymentStarted,
    DeploymentCompleted,
    DeploymentSucceeded,
    DeploymentFailed,
    DeploymentRolledBack,
    ExperimentStarted,
    VariantAssigned,
    ExperimentConcluded,
    ExperimentCompleted,
    MCPServerRegistered,
    MCPServerUpdated,
    MCPServerRemoved,
    RegulationCreated,
    RegulationUpdated,
    RegulationRemoved,
    CompliancePolicyCreated,
    CompliancePolicyUpdated,
    CompliancePolicyRemoved,
    ProcedureCreated,
    ProcedureUpdated,
    ProcedureRemoved,
    PracticeCreated,
    PracticeUpdated,
    PracticeRemoved,
    StrategyCreated,
    StrategyUpdated,
    StrategyRemoved,
    KPICreated,
    KPIUpdated,
    KPIRemoved,
    ComplianceExperimentCreated,
    ComplianceExperimentUpdated,
    ComplianceExperimentRemoved,
    ComplianceMetricCreated,
    ComplianceMetricUpdated,
    ComplianceMetricRemoved,
    RunMetricRecorded,
    StrategyMutationSuggested,
    TournamentCompleted,
    KnowledgeEntryCreated,
    KnowledgeEntryUpdated,
    KnowledgeEntryRemoved,
    KnowledgeExtractionStarted,
    KnowledgeExtractionCompleted,
    KnowledgeExtractionFailed,
    ArchitectureDecisionCreated,
    ArchitectureDecisionUpdated,
    ArchitectureDecisionRemoved,
    HumanApprovalGranted,
    HumanApprovalRejected,
    ResourceVersionProduced,
    ResourceVersionConsumed,
    DeliveryLoopStarted,
    DeliveryLoopPhaseTransitioned,
    LearningCaptured,
    DeliveryLoopAborted,
    DeliveryCheckpointReached,
    DeliveryLoopCompleted,
    HookTriggered,
    HookExecutionFailed,
    HookLoopDetected,
    PreHookBlocked,
    PreHookAllowed,
    PolicyImportedFromGDrive,
    PolicyGenerationStarted,
    PolicyGenerationCompleted,
    PolicyGenerationFailed,
    FeedbackReceived,
    FeedbackCategorized,
    FeedbackWorkItemCreated,
    CodebaseConnected,
    CodebaseIndexed,
    CodebaseReindexed,
    DriftDetected,
    DriftResolved,
    DriftEscalated,
    DriftRuleCreated,
    DriftRuleUpdated,
    DriftRuleRemoved,
    DriftScanStarted,
    DriftScanCompleted,
    GovernancePolicyCreated,
    GovernancePolicyUpdated,
    GovernancePolicyRemoved,
    AgentActionAllowed,
    AgentActionDenied,
    AgentActionApprovalRequested,
    AttachmentUploaded,
    AttachmentLinked,
    AttachmentRemoved,
    MetricVisibilitySet,
    MetricVisibilityRemoved,
    PrivacyPreferenceUpdated,
    FirewallRuleCreated,
    FirewallRuleUpdated,
    FirewallRuleRemoved,
    AgentRequestBlocked,
    AgentRequestAllowed,
    AgentSkillCreated,
    AgentSkillUpdated,
    AgentSkillRemoved,
    AgentSkillBound,
    AgentSkillUnbound,
    SlackNotificationSent,
    SlackNotificationFailed,
    SlackNotificationTemplateCreated,
    SlackNotificationTemplateUpdated,
    SlackInvocationReceived,
    SlackWorkflowDispatched,
    SlackWorkflowCompleted,
    WorkflowBlueprintCreated,
    WorkflowBlueprintUpdated,
    WorkflowBlueprintRemoved,
    WorkflowBlueprintActivated,
    WorkflowBlueprintDeactivated,
    SandboxImageBuilt,
    SandboxImageExpired,
    PooledSandboxWarmed,
    PooledSandboxAssigned,
    PooledSandboxReleased,
    SandboxImageRebuildStarted,
    SandboxImageRebuildCompleted,
    SandboxImageRebuildFailed,
    SandboxSnapshotCreated,
    SandboxSnapshotRestored,
    SandboxSnapshotExpired,
    CodingRuleCreated,
    CodingRuleUpdated,
    CodingRuleRemoved,
    RuleViolationDetected,
    RuleViolationResolved,
)
