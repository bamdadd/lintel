"""Audit projection — builds an audit trail from domain events.

Every domain event that represents a state change (create, update, delete,
invoke, approve, reject, …) is projected into an ``AuditEntry`` in the
audit store.  The same events can be consumed by other projections for
webhooks, notifications, or analytics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()

# Maps event_type → (action, resource_type) for the audit entry.
# Events not listed here are silently ignored by the projection.
_EVENT_TO_AUDIT: dict[str, tuple[str, str]] = {
    # Projects
    "ProjectCreated": ("create", "project"),
    "ProjectUpdated": ("update", "project"),
    "ProjectArchived": ("archive", "project"),
    "ProjectRemoved": ("delete", "project"),
    # Repositories
    "RepositoryRegistered": ("create", "repository"),
    "RepositoryUpdated": ("update", "repository"),
    "RepositoryRemoved": ("delete", "repository"),
    # Users
    "UserCreated": ("create", "user"),
    "UserUpdated": ("update", "user"),
    "UserRemoved": ("delete", "user"),
    # Teams
    "TeamCreated": ("create", "team"),
    "TeamUpdated": ("update", "team"),
    "TeamRemoved": ("delete", "team"),
    # Work items
    "WorkItemCreated": ("create", "work_item"),
    "WorkItemUpdated": ("update", "work_item"),
    "WorkItemCompleted": ("complete", "work_item"),
    "WorkItemRemoved": ("delete", "work_item"),
    # Pipelines
    "PipelineRunStarted": ("start", "pipeline"),
    "PipelineRunCompleted": ("complete", "pipeline"),
    "PipelineRunFailed": ("fail", "pipeline"),
    "PipelineRunCancelled": ("cancel", "pipeline"),
    "PipelineRunDeleted": ("delete", "pipeline"),
    "PipelineStageCompleted": ("complete_stage", "pipeline_stage"),
    "PipelineStageApproved": ("approve", "pipeline_stage"),
    "PipelineStageRejected": ("reject", "pipeline_stage"),
    "PipelineStageRetried": ("retry", "pipeline_stage"),
    # Credentials
    "CredentialStored": ("create", "credential"),
    "CredentialRevoked": ("revoke", "credential"),
    # Sandboxes
    "SandboxCreated": ("create", "sandbox"),
    "SandboxCommandExecuted": ("execute", "sandbox"),
    "SandboxFileWritten": ("write_file", "sandbox"),
    "SandboxDestroyed": ("destroy", "sandbox"),
    # AI Providers & Models
    "AIProviderCreated": ("create", "ai_provider"),
    "AIProviderUpdated": ("update", "ai_provider"),
    "AIProviderRemoved": ("delete", "ai_provider"),
    "AIProviderApiKeyUpdated": ("update_api_key", "ai_provider"),
    "ModelRegistered": ("create", "model"),
    "ModelUpdated": ("update", "model"),
    "ModelRemoved": ("delete", "model"),
    "ModelAssignmentCreated": ("create", "model_assignment"),
    "ModelAssignmentRemoved": ("delete", "model_assignment"),
    # Environments
    "EnvironmentCreated": ("create", "environment"),
    "EnvironmentUpdated": ("update", "environment"),
    "EnvironmentRemoved": ("delete", "environment"),
    # Triggers
    "TriggerCreated": ("create", "trigger"),
    "TriggerUpdated": ("update", "trigger"),
    "TriggerRemoved": ("delete", "trigger"),
    "TriggerFired": ("fire", "trigger"),
    # Variables
    "VariableCreated": ("create", "variable"),
    "VariableUpdated": ("update", "variable"),
    "VariableRemoved": ("delete", "variable"),
    # Workflow definitions
    "WorkflowDefinitionCreated": ("create", "workflow_definition"),
    "WorkflowDefinitionUpdated": ("update", "workflow_definition"),
    "WorkflowDefinitionRemoved": ("delete", "workflow_definition"),
    # Skills
    "SkillRegistered": ("register", "skill"),
    "SkillUpdated": ("update", "skill"),
    "SkillRemoved": ("delete", "skill"),
    "SkillInvoked": ("invoke", "skill"),
    # Approvals
    "HumanApprovalGranted": ("grant", "approval"),
    "HumanApprovalRejected": ("reject", "approval"),
    "ApprovalRequested": ("request", "approval"),
    "ApprovalRequestCreated": ("create", "approval_request"),
    "ApprovalRequestApproved": ("approve", "approval_request"),
    "ApprovalRequestRejected": ("reject", "approval_request"),
    # Notifications
    "NotificationRuleCreated": ("create", "notification_rule"),
    "NotificationRuleUpdated": ("update", "notification_rule"),
    "NotificationRuleRemoved": ("delete", "notification_rule"),
    # MCP Servers
    "MCPServerRegistered": ("register", "mcp_server"),
    "MCPServerUpdated": ("update", "mcp_server"),
    "MCPServerRemoved": ("delete", "mcp_server"),
    # Policies
    "PolicyCreated": ("create", "policy"),
    "PolicyUpdated": ("update", "policy"),
    "PolicyRemoved": ("delete", "policy"),
    # Connections & Settings
    "ConnectionCreated": ("create", "connection"),
    "ConnectionUpdated": ("update", "connection"),
    "ConnectionRemoved": ("delete", "connection"),
    "SettingsUpdated": ("update", "settings"),
    # Conversations
    "ConversationCreated": ("create", "conversation"),
    "ConversationDeleted": ("delete", "conversation"),
    "WorkflowTriggered": ("workflow_started", "work_item"),
    "ProjectSelected": ("project_selected", "conversation"),
    # Agent definitions
    "AgentDefinitionCreated": ("create", "agent_definition"),
    "AgentDefinitionUpdated": ("update", "agent_definition"),
    "AgentDefinitionRemoved": ("delete", "agent_definition"),
    # Security
    "VaultRevealRequested": ("reveal_request", "pii_vault"),
    "VaultRevealGranted": ("reveal_grant", "pii_vault"),
    # Git operations
    "RepoCloned": ("clone", "repository"),
    "BranchCreated": ("create_branch", "repository"),
    "CommitPushed": ("push", "repository"),
    "PRCreated": ("create", "pull_request"),
    "PRCommentAdded": ("comment", "pull_request"),
    # Workflows
    "WorkflowStarted": ("start", "workflow"),
    "WorkflowAdvanced": ("advance", "workflow"),
    "IntentRouted": ("route", "intent"),
}


class AuditProjection:
    """Consumes domain events and writes audit entries.

    The audit store is injected at construction time. When the projection
    receives an event whose ``event_type`` is in ``_EVENT_TO_AUDIT``, it
    creates an ``AuditEntry`` and persists it.
    """

    def __init__(self, audit_store: Any) -> None:  # noqa: ANN401
        self._audit_store = audit_store

    @property
    def name(self) -> str:
        return "audit"

    def get_state(self) -> dict[str, Any]:
        return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        pass

    @property
    def handled_event_types(self) -> set[str]:
        return set(_EVENT_TO_AUDIT.keys())

    async def project(self, event: EventEnvelope) -> None:
        mapping = _EVENT_TO_AUDIT.get(event.event_type)
        if mapping is None:
            return

        action, resource_type = mapping
        resource_id = (
            event.payload.get("resource_id")
            or event.payload.get("id")
            or event.payload.get("run_id")
            or event.payload.get("project_id")
            or ""
        )

        from lintel.contracts.types import AuditEntry

        entry = AuditEntry(
            entry_id=uuid4().hex,
            actor_id=event.actor_id or "system",
            actor_type=event.actor_type.value
            if hasattr(event.actor_type, "value")
            else str(event.actor_type),
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=event.payload,
            timestamp=event.occurred_at.isoformat(),
        )

        try:
            await self._audit_store.add(entry)
        except Exception:
            logger.warning(
                "audit_projection_write_failed",
                event_type=event.event_type,
                entry_id=entry.entry_id,
            )

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)
