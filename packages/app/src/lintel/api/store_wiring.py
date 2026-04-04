"""Store factory functions and StoreProvider wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

from lintel.agent_definitions_api.routes import agent_definition_store_provider
from lintel.agent_definitions_api.store import AgentDefinitionStore
from lintel.agent_skills_api.routes import (
    agent_skill_binding_store_provider,
    agent_skill_store_provider,
)
from lintel.agent_skills_api.store import InMemoryAgentSkillBindingStore, InMemoryAgentSkillStore
from lintel.ai_firewall_api.routes import firewall_log_store_provider, firewall_rule_store_provider
from lintel.ai_firewall_api.store import InMemoryFirewallLogStore, InMemoryFirewallRuleStore
from lintel.ai_providers_api.routes import ai_provider_store_provider
from lintel.ai_providers_api.routes import model_store_provider as ai_providers_model_store_provider
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.approval_requests_api.routes import approval_request_store_provider
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
from lintel.artifacts_api.routes import (
    artifact_content_store_provider,
    code_artifact_store_provider,
    coverage_metric_store_provider,
    parsed_result_store_provider,
    quality_gate_rule_store_provider,
    test_result_store_provider,
)
from lintel.artifacts_api.routes import (
    pipeline_store_provider as artifact_pipeline_store_provider,
)
from lintel.artifacts_api.store import (
    CodeArtifactStore,
    CoverageMetricStore,
    ParsedTestResultStore,
    QualityGateRuleStore,
    TestResultStore,
)
from lintel.audit_api.routes import audit_entry_store_provider
from lintel.audit_api.store import AuditEntryStore
from lintel.auth_api.routes import auth_user_store_provider, session_store_provider
from lintel.auth_api.store import InMemoryAuthUserStore, InMemorySessionStore
from lintel.automations_api.routes import InMemoryAutomationStore, automation_store_provider
from lintel.board_sync_api.routes import (
    mapping_store_provider as board_sync_mapping_store_provider,
)
from lintel.board_sync_api.routes import (
    sync_config_store_provider as board_sync_config_store_provider,
)
from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore
from lintel.boards.routes import board_store_provider, tag_store_provider
from lintel.boards.store import BoardStore, TagStore
from lintel.channel_connections_api.routes import connection_store_provider
from lintel.channel_connections_api.store import InMemoryChannelConnectionStore
from lintel.chat_api.routes import ChatStore, chat_store_provider
from lintel.chat_api.streaming import chat_stream_store_provider
from lintel.codebase_index_api.routes import index_store_provider as codebase_index_store_provider
from lintel.codebase_index_api.store import InMemoryCodebaseIndexStore
from lintel.coding_rules_api.routes import coding_rule_store_provider, violation_store_provider
from lintel.coding_rules_api.store import InMemoryCodingRuleStore, InMemoryRuleViolationStore
from lintel.compliance_api.routes import (
    architecture_decision_store_provider,
    compliance_policy_store_provider,
    guardrail_rule_store_provider,
    knowledge_entry_store_provider,
    knowledge_extraction_store_provider,
    policy_generation_store_provider,
    practice_store_provider,
    procedure_store_provider,
    regulation_store_provider,
    strategy_store_provider,
)
from lintel.compliance_api.store import ComplianceStore
from lintel.context_attachments_api.routes import attachment_store_provider
from lintel.context_attachments_api.store import InMemoryAttachmentStore
from lintel.credentials_api.routes import credential_store_provider
from lintel.credentials_api.store import InMemoryCredentialStore
from lintel.cve_remediation_api.routes import (
    advisory_store_provider,
    plan_store_provider,
    result_store_provider,
)
from lintel.cve_remediation_api.store import (
    InMemoryCveAdvisoryStore,
    InMemoryRemediationPlanStore,
    InMemoryRemediationResultStore,
)
from lintel.digest_api.routes import (
    digest_config_store_provider,
    digest_store_provider,
)
from lintel.digest_api.routes import (
    pipeline_store_provider as digest_pipeline_store_provider,
)
from lintel.digest_api.routes import (
    work_item_store_provider as digest_work_item_store_provider,
)
from lintel.digest_api.store import InMemoryDigestConfigStore, InMemoryDigestStore
from lintel.drift_detection_api.routes import (
    drift_alert_store_provider,
    drift_rule_store_provider,
    drift_scan_store_provider,
)
from lintel.drift_detection_api.store import (
    InMemoryDriftAlertStore,
    InMemoryDriftRuleStore,
    InMemoryDriftScanStore,
)
from lintel.environments_api.routes import environment_store_provider
from lintel.environments_api.store import InMemoryEnvironmentStore
from lintel.event_store.in_memory import InMemoryEventStore
from lintel.experimentation_api.routes import (
    compliance_metric_store_provider,
    experiment_store_provider,
    kpi_store_provider,
    mutation_store_provider,
    run_metric_store_provider,
    tournament_store_provider,
)
from lintel.feedback_api.routes import feedback_store_provider
from lintel.feedback_api.store import InMemoryFeedbackStore
from lintel.governance_api.routes import (
    governance_audit_store_provider,
    governance_policy_store_provider,
)
from lintel.improvement_api.routes import improvement_store_provider
from lintel.improvement_api.store import InMemoryImprovementStore
from lintel.integration_patterns_api.routes import integration_pattern_store_provider
from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore
from lintel.mcp_servers_api.routes import (
    mcp_server_store_provider,
    mcp_tool_allowlist_store_provider,
    mcp_tool_store_provider,
)
from lintel.mcp_servers_api.store import (
    InMemoryMCPServerStore,
    MCPToolAllowlistStore,
    MCPToolStore,
)
from lintel.memory_api.dependencies import memory_service_provider
from lintel.models_api.routes import ai_provider_store_provider as models_ai_provider_store_provider
from lintel.models_api.routes import model_assignment_store_provider, model_store_provider
from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore
from lintel.notifications_api.routes import notification_rule_store_provider
from lintel.notifications_api.store import NotificationRuleStore
from lintel.pipelines_api.routes import InMemoryPipelineStore, pipeline_store_provider
from lintel.policies_api.routes import policy_store_provider
from lintel.policies_api.store import InMemoryPolicyStore
from lintel.privacy_controls_api.routes import (
    preference_store_provider,
    visibility_store_provider,
)
from lintel.privacy_controls_api.store import InMemoryPreferenceStore, InMemoryVisibilityStore
from lintel.process_mining_api.routes import process_mining_store_provider
from lintel.process_mining_api.store import InMemoryProcessMiningStore
from lintel.projects_api.routes import project_store_provider
from lintel.projects_api.store import ProjectStore
from lintel.release_notes_api.routes import (
    release_note_store_provider,
)
from lintel.release_notes_api.routes import (
    repo_provider_provider as release_notes_repo_provider,
)
from lintel.release_notes_api.store import InMemoryReleaseNoteStore
from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repositories_api.routes import repo_provider_provider, repository_store_provider
from lintel.sandbox_credentials_api.routes import (
    sandbox_credential_store_provider,
)
from lintel.sandbox_credentials_api.store import InMemorySandboxCredentialStore
from lintel.sandbox_pool_api.routes import (
    image_rebuild_store_provider,
    pooled_sandbox_store_provider,
    sandbox_image_store_provider,
    sandbox_pool_config_store_provider,
)
from lintel.sandbox_pool_api.store import (
    InMemoryImageRebuildStore,
    InMemoryPooledSandboxStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)
from lintel.sandboxes_api.replica_store import InMemoryReplicaConfigStore
from lintel.sandboxes_api.routes import (
    SandboxStore,
    replica_config_store_provider,
    snapshot_store_provider,
)
from lintel.sandboxes_api.snapshot_store import InMemorySnapshotStore
from lintel.scheduled_tasks_api.routes import scheduled_task_store_provider
from lintel.scheduled_tasks_api.store import InMemoryScheduledTaskStore
from lintel.skills_api.routes import skill_store_provider
from lintel.skills_api.store import InMemorySkillStore
from lintel.slack_notifications_api.routes import (
    record_store_provider as slack_notification_record_store_provider,
)
from lintel.slack_notifications_api.routes import (
    template_store_provider as slack_notification_template_store_provider,
)
from lintel.slack_notifications_api.store import (
    InMemorySlackNotificationRecordStore,
    InMemorySlackNotificationTemplateStore,
)
from lintel.slack_workflows_api.routes import invocation_store_provider
from lintel.slack_workflows_api.store import InMemorySlackInvocationStore
from lintel.teams.routes import team_store_provider
from lintel.teams.store import InMemoryTeamStore
from lintel.triggers_api.routes import trigger_store_provider
from lintel.triggers_api.store import InMemoryTriggerStore
from lintel.trust_scores_api.routes import trust_score_store_provider
from lintel.trust_scores_api.store import InMemoryTrustScoreStore
from lintel.users.routes import user_store_provider
from lintel.users.store import InMemoryUserStore
from lintel.variables_api.routes import variable_store_provider
from lintel.variables_api.store import InMemoryVariableStore
from lintel.visual_verification_api.routes import verification_store_provider
from lintel.visual_verification_api.store import InMemoryVisualVerificationStore
from lintel.work_items_api.routes import work_item_store_provider
from lintel.work_items_api.store import WorkItemStore
from lintel.workflow_blueprints_api.routes import blueprint_store_provider
from lintel.workflow_blueprints_api.store import InMemoryWorkflowBlueprintStore
from lintel.workflow_definitions_api.routes import workflow_definition_store_provider
from lintel.workflow_definitions_api.store import InMemoryWorkflowDefinitionStore


def _dc_to_dict(obj: Any) -> dict[str, Any]:  # noqa: ANN401
    """Convert a frozen dataclass to a dict, handling nested tuples."""
    from dataclasses import asdict

    d = asdict(obj)
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d


def _create_fake_artifact_content_store() -> Any:  # noqa: ANN401
    """Create an in-memory FakeArtifactStore for dev mode."""
    from lintel.contracts.protocols.artifact_store import ArtifactRef

    class _InMemoryArtifactContentStore:
        def __init__(self) -> None:
            self._content: dict[str, bytes] = {}
            self._refs: dict[str, ArtifactRef] = {}

        async def store(
            self,
            artifact_id: str,
            content: bytes,
            metadata: dict[str, object],
        ) -> str:
            self._content[artifact_id] = content
            self._refs[artifact_id] = ArtifactRef(
                artifact_id=artifact_id,
                storage_backend="postgres",
                location=f"mem://{artifact_id}",
                size_bytes=len(content),
                content_type=str(metadata.get("content_type", "application/octet-stream")),
                pipeline_run_id=str(metadata.get("pipeline_run_id", "")),
            )
            return f"mem://{artifact_id}"

        async def retrieve(self, artifact_id: str) -> bytes:
            if artifact_id not in self._content:
                msg = f"Artifact {artifact_id} not found"
                raise KeyError(msg)
            return self._content[artifact_id]

        async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
            return [r for r in self._refs.values() if r.pipeline_run_id == pipeline_run_id]

    return _InMemoryArtifactContentStore()


def create_in_memory_stores() -> dict[str, Any]:
    """Create all in-memory stores for development without a database."""
    return {
        "event_store": InMemoryEventStore(),
        "repository_store": InMemoryRepositoryStore(),
        "skill_store": InMemorySkillStore(),
        "credential_store": InMemoryCredentialStore(),
        "ai_provider_store": InMemoryAIProviderStore(),
        "project_store": ProjectStore(),
        "work_item_store": WorkItemStore(),
        "pipeline_store": InMemoryPipelineStore(),
        "environment_store": InMemoryEnvironmentStore(),
        "trigger_store": InMemoryTriggerStore(),
        "automation_store": InMemoryAutomationStore(),
        "variable_store": InMemoryVariableStore(),
        "digest_store": InMemoryDigestStore(),
        "digest_config_store": InMemoryDigestConfigStore(),
        "user_store": InMemoryUserStore(),
        "release_note_store": InMemoryReleaseNoteStore(),
        "team_store": InMemoryTeamStore(),
        "policy_store": InMemoryPolicyStore(),
        "notification_rule_store": NotificationRuleStore(),
        "audit_entry_store": AuditEntryStore(),
        "code_artifact_store": CodeArtifactStore(),
        "artifact_content_store": _create_fake_artifact_content_store(),
        "test_result_store": TestResultStore(),
        "parsed_result_store": ParsedTestResultStore(),
        "coverage_metric_store": CoverageMetricStore(),
        "quality_gate_rule_store": QualityGateRuleStore(),
        "approval_request_store": InMemoryApprovalRequestStore(),
        "chat_store": ChatStore(),
        "agent_definition_store": AgentDefinitionStore(),
        "model_store": InMemoryModelStore(),
        "model_assignment_store": InMemoryModelAssignmentStore(),
        "mcp_server_store": InMemoryMCPServerStore(),
        "mcp_tool_store": MCPToolStore(),
        "mcp_tool_allowlist_store": MCPToolAllowlistStore(),
        "sandbox_store": SandboxStore(),
        "tag_store": TagStore(),
        "board_store": BoardStore(),
        "integration_patterns": InMemoryIntegrationPatternStore(),
        "process_mining": InMemoryProcessMiningStore(),
        "workflow_definition_store": InMemoryWorkflowDefinitionStore(),
        # Compliance & Governance stores
        "regulation_store": ComplianceStore("regulation_id"),
        "compliance_policy_store": ComplianceStore("policy_id"),
        "procedure_store": ComplianceStore("procedure_id"),
        "practice_store": ComplianceStore("practice_id"),
        "strategy_store": ComplianceStore("strategy_id"),
        "kpi_store": ComplianceStore("kpi_id"),
        "experiment_store": ComplianceStore("experiment_id"),
        "compliance_metric_store": ComplianceStore("metric_id"),
        "drift_rule_store": InMemoryDriftRuleStore(),
        "drift_alert_store": InMemoryDriftAlertStore(),
        "drift_scan_store": InMemoryDriftScanStore(),
        "run_metric_store": ComplianceStore("run_metric_id"),
        "mutation_store": ComplianceStore("mutation_id"),
        "tournament_store": ComplianceStore("tournament_id"),
        "feedback_store": InMemoryFeedbackStore(),
        "improvement_store": InMemoryImprovementStore(),
        "codebase_index_store": InMemoryCodebaseIndexStore(),
        "knowledge_entry_store": ComplianceStore("entry_id"),
        "knowledge_extraction_store": ComplianceStore("run_id"),
        "architecture_decision_store": ComplianceStore("decision_id"),
        "policy_generation_store": ComplianceStore("run_id"),
        "guardrail_rule_store": ComplianceStore("rule_id"),
        # Composable Agent Skills stores (REQ-F033)
        "agent_skill_store": InMemoryAgentSkillStore(),
        "agent_skill_binding_store": InMemoryAgentSkillBindingStore(),
        # Agent Trust Score store (REQ-F029)
        "trust_score_store": InMemoryTrustScoreStore(),
        # Privacy Controls stores (REQ-008)
        "visibility_store": InMemoryVisibilityStore(),
        "preference_store": InMemoryPreferenceStore(),
        # AI Firewall stores (REQ-025)
        "firewall_rule_store": InMemoryFirewallRuleStore(),
        "firewall_log_store": InMemoryFirewallLogStore(),
        # Slack Notification stores
        "slack_notification_template_store": InMemorySlackNotificationTemplateStore(),
        "slack_notification_record_store": InMemorySlackNotificationRecordStore(),
        # Agent Action Governance stores (REQ-030)
        "governance_policy_store": ComplianceStore("policy_id"),
        "governance_audit_store": ComplianceStore("entry_id"),
        "attachment_store": InMemoryAttachmentStore(),
        # Slack Workflow Invocations
        "slack_invocation_store": InMemorySlackInvocationStore(),
        # Coding Rules stores
        "coding_rule_store": InMemoryCodingRuleStore(),
        "violation_store": InMemoryRuleViolationStore(),
        # Workflow Blueprints
        "workflow_blueprint_store": InMemoryWorkflowBlueprintStore(),
        # Sandbox Pool stores
        "sandbox_image_store": InMemorySandboxImageStore(),
        "pooled_sandbox_store": InMemoryPooledSandboxStore(),
        "sandbox_pool_config_store": InMemorySandboxPoolConfigStore(),
        "image_rebuild_store": InMemoryImageRebuildStore(),
        # Sandbox Snapshots
        "snapshot_store": InMemorySnapshotStore(),
        # Sandbox Replica Configs
        "replica_config_store": InMemoryReplicaConfigStore(),
        # Channel Connections
        "channel_connection_store": InMemoryChannelConnectionStore(),
        # Visual Verification
        "visual_verification_store": InMemoryVisualVerificationStore(),
        # Sandbox Credentials
        "sandbox_credential_store": InMemorySandboxCredentialStore(),
        # Scheduled Tasks
        "scheduled_task_store": InMemoryScheduledTaskStore(),
        # CVE Remediation
        "cve_advisory_store": InMemoryCveAdvisoryStore(),
        "remediation_plan_store": InMemoryRemediationPlanStore(),
        "remediation_result_store": InMemoryRemediationResultStore(),
        # Board Sync stores
        "board_sync_config_store": BoardSyncConfigStore(),
        "external_id_mapping_store": ExternalIdMappingStore(),
    }


def _create_postgres_artifact_content_store(pool: asyncpg.Pool) -> Any:  # noqa: ANN401
    """Create an artifact content store based on LINTEL_ARTIFACT_* settings.

    Supports three modes:
    - ``postgres`` (default): inline content in Postgres JSONB
    - ``s3``: all content in S3/MinIO with metadata in Postgres
    - ``routing``: auto-routes by size threshold (small → Postgres, large → S3)
    """
    import os

    from lintel.infrastructure.stores.postgres_artifact_store import (
        PostgresArtifactStore as PgArtifactContentStore,
    )

    backend = os.environ.get("LINTEL_ARTIFACT_STORAGE_BACKEND", "postgres").lower()

    pg_store = PgArtifactContentStore(pool)

    if backend in ("s3", "routing"):
        import aioboto3

        from lintel.infrastructure.stores.object_artifact_store import ObjectArtifactStore

        bucket = os.environ.get("LINTEL_ARTIFACT_S3_BUCKET", "artifacts")
        endpoint_url = os.environ.get("LINTEL_ARTIFACT_S3_ENDPOINT_URL")

        session = aioboto3.Session(
            aws_access_key_id=os.environ.get("LINTEL_ARTIFACT_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("LINTEL_ARTIFACT_S3_SECRET_ACCESS_KEY"),
        )
        obj_store = ObjectArtifactStore(
            session=session,
            pool=pool,
            bucket=bucket,
            endpoint_url=endpoint_url,
        )

        if backend == "s3":
            return obj_store

        # routing mode
        from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

        threshold = int(
            os.environ.get("LINTEL_ARTIFACT_SIZE_THRESHOLD_BYTES", "1048576"),
        )
        return RoutingArtifactStore(
            postgres_store=pg_store,
            object_store=obj_store,
            size_threshold_bytes=threshold,
        )

    return pg_store


def create_postgres_stores(pool: asyncpg.Pool) -> dict[str, Any]:
    """Create all Postgres-backed stores."""
    from lintel.event_store.postgres import PostgresEventStore
    from lintel.integration_patterns_api.postgres_store import (
        PostgresIntegrationPatternStore as _PgIntegrationPatternStore,
    )
    from lintel.persistence.dict_store import PostgresComplianceStore as PgCompliance
    from lintel.persistence.pg_stores import (
        PostgresAgentSkillBindingStore as _PgAgentSkillBindingStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresAgentSkillStore as _PgAgentSkillStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresAttachmentStore as _PgAttachmentStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresChannelConnectionStore as _PgChannelConnectionStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresCodebaseIndexStore as _PgCodebaseIndexStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresCodingRuleStore as _PgCodingRuleStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresCoverageMetricStore as _PgCoverageMetricStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresDigestConfigStore as _PgDigestConfigStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresDigestStore as _PgDigestStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresDriftAlertStore as _PgDriftAlertStoreImpl,
    )
    from lintel.persistence.pg_stores import (
        PostgresDriftRuleStore as _PgDriftRuleStoreImpl,
    )
    from lintel.persistence.pg_stores import (
        PostgresDriftScanStore as _PgDriftScanStoreImpl,
    )
    from lintel.persistence.pg_stores import (
        PostgresFirewallLogStore as _PgFirewallLogStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresFirewallRuleStore as _PgFirewallRuleStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresImageRebuildStore as _PgImageRebuildStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresMCPToolAllowlistStore as _PgMCPToolAllowlistStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresMCPToolStore as _PgMCPToolStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresParsedTestResultStore as _PgParsedTestResultStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresPooledSandboxStore as _PgPooledSandboxStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresPreferenceStore as _PgPreferenceStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresQualityGateRuleStore as _PgQualityGateRuleStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresReleaseNoteStore as _PgReleaseNoteStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresRuleViolationStore as _PgRuleViolationStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSandboxCredentialStore as _PgSandboxCredentialStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSandboxImageStore as _PgSandboxImageStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSandboxPoolConfigStore as _PgSandboxPoolConfigStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresScheduledTaskStore as _PgScheduledTaskStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSlackInvocationStore as _PgSlackInvocationStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSlackNotificationRecordStore as _PgSlackNotifRecordStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSlackNotificationTemplateStore as _PgSlackNotifTemplateStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresSnapshotStore as _PgSnapshotStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresTrustScoreStore as _PgTrustScoreStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresVisibilityStore as _PgVisibilityStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresVisualVerificationStore as _PgVisualVerificationStore,
    )
    from lintel.persistence.pg_stores import (
        PostgresWorkflowBlueprintStore as _PgWorkflowBlueprintStore,
    )
    from lintel.persistence.stores import (
        PostgresAgentDefinitionStore,
        PostgresAIProviderStore,
        PostgresApprovalRequestStore,
        PostgresAuditEntryStore,
        PostgresAutomationStore,
        PostgresChatStore,
        PostgresCodeArtifactStore,
        PostgresCredentialStore,
        PostgresEnvironmentStore,
        PostgresMCPServerStore,
        PostgresModelAssignmentStore,
        PostgresModelStore,
        PostgresNotificationRuleStore,
        PostgresPipelineStore,
        PostgresPolicyStore,
        PostgresProjectStore,
        PostgresRepositoryStore,
        PostgresSandboxStore,
        PostgresSkillStore,
        PostgresTeamStore,
        PostgresTestResultStore,
        PostgresTriggerStore,
        PostgresUserStore,
        PostgresVariableStore,
        PostgresWorkItemStore,
    )
    from lintel.persistence.stores import (
        PostgresBoardStore as _PgBoardStore,
    )
    from lintel.persistence.stores import (
        PostgresTagStore as _PgTagStore,
    )
    from lintel.process_mining_api.postgres_store import (
        PostgresProcessMiningStore as _PgProcessMiningStore,
    )
    from lintel.workflow_definitions_api.store import PostgresWorkflowDefinitionStore

    class _BoardStoreAdapter:
        """Adapt PostgresCrudStore (dataclass) to dict-based interface used by routes."""

        def __init__(self, pg: _PgBoardStore) -> None:
            self._pg = pg

        async def add(self, data: dict[str, Any]) -> None:
            from lintel.domain.types import Board, BoardColumn

            cols = tuple(
                BoardColumn(
                    column_id=c["column_id"],
                    name=c.get("name", ""),
                    position=c.get("position", 0),
                    work_item_statuses=tuple(c.get("work_item_statuses", ())),
                    wip_limit=c.get("wip_limit", 0),
                )
                for c in data.get("columns", [])
            )
            entity = Board(
                board_id=data["board_id"],
                project_id=data.get("project_id", ""),
                name=data.get("name", ""),
                columns=cols,
                auto_move=data.get("auto_move", False),
            )
            await self._pg.add(entity)

        async def get(self, board_id: str) -> dict[str, Any] | None:
            result = await self._pg.get(board_id)
            if result is None:
                return None
            return _dc_to_dict(result)

        async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
            items = await self._pg.list_by_project(project_id)
            return [_dc_to_dict(i) for i in items]

        async def update(self, board_id: str, data: dict[str, Any]) -> None:
            from lintel.domain.types import Board, BoardColumn

            cols = tuple(
                BoardColumn(
                    column_id=c["column_id"],
                    name=c.get("name", ""),
                    position=c.get("position", 0),
                    work_item_statuses=tuple(c.get("work_item_statuses", ())),
                    wip_limit=c.get("wip_limit", 0),
                )
                for c in data.get("columns", [])
            )
            entity = Board(
                board_id=board_id,
                project_id=data.get("project_id", ""),
                name=data.get("name", ""),
                columns=cols,
                auto_move=data.get("auto_move", False),
            )
            await self._pg.update(entity)

        async def remove(self, board_id: str) -> None:
            await self._pg.remove(board_id)

    class _TagStoreAdapter:
        def __init__(self, pg: _PgTagStore) -> None:
            self._pg = pg

        async def add(self, data: dict[str, Any]) -> None:
            from lintel.domain.types import Tag

            entity = Tag(
                tag_id=data["tag_id"],
                project_id=data.get("project_id", ""),
                name=data.get("name", ""),
                color=data.get("color", "#6b7280"),
            )
            await self._pg.add(entity)

        async def get(self, tag_id: str) -> dict[str, Any] | None:
            result = await self._pg.get(tag_id)
            if result is None:
                return None
            return _dc_to_dict(result)

        async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
            items = await self._pg.list_by_project(project_id)
            return [_dc_to_dict(i) for i in items]

        async def update(self, tag_id: str, data: dict[str, Any]) -> None:
            from lintel.domain.types import Tag

            entity = Tag(
                tag_id=tag_id,
                project_id=data.get("project_id", ""),
                name=data.get("name", ""),
                color=data.get("color", "#6b7280"),
            )
            await self._pg.update(entity)

        async def remove(self, tag_id: str) -> None:
            await self._pg.remove(tag_id)

    return {
        "event_store": PostgresEventStore(pool),
        "repository_store": PostgresRepositoryStore(pool),
        "skill_store": PostgresSkillStore(pool),
        "credential_store": PostgresCredentialStore(pool),
        "ai_provider_store": PostgresAIProviderStore(pool),
        "project_store": PostgresProjectStore(pool),
        "work_item_store": PostgresWorkItemStore(pool),
        "pipeline_store": PostgresPipelineStore(pool),
        "environment_store": PostgresEnvironmentStore(pool),
        "trigger_store": PostgresTriggerStore(pool),
        "automation_store": PostgresAutomationStore(pool),
        "variable_store": PostgresVariableStore(pool),
        "user_store": PostgresUserStore(pool),
        "team_store": PostgresTeamStore(pool),
        "policy_store": PostgresPolicyStore(pool),
        "notification_rule_store": PostgresNotificationRuleStore(pool),
        "audit_entry_store": PostgresAuditEntryStore(pool),
        "code_artifact_store": PostgresCodeArtifactStore(pool),
        "artifact_content_store": _create_postgres_artifact_content_store(pool),
        "test_result_store": PostgresTestResultStore(pool),
        "approval_request_store": PostgresApprovalRequestStore(pool),
        "chat_store": PostgresChatStore(pool),
        "agent_definition_store": PostgresAgentDefinitionStore(pool),
        "model_store": PostgresModelStore(pool),
        "model_assignment_store": PostgresModelAssignmentStore(pool),
        "mcp_server_store": PostgresMCPServerStore(pool),
        "sandbox_store": PostgresSandboxStore(pool),
        "tag_store": _TagStoreAdapter(_PgTagStore(pool)),
        "board_store": _BoardStoreAdapter(_PgBoardStore(pool)),
        # Compliance & Governance stores (Postgres-backed)
        "regulation_store": PgCompliance(pool, "regulation", "regulation_id"),
        "compliance_policy_store": PgCompliance(pool, "compliance_policy", "policy_id"),
        "procedure_store": PgCompliance(pool, "procedure", "procedure_id"),
        "practice_store": PgCompliance(pool, "practice", "practice_id"),
        "strategy_store": PgCompliance(pool, "strategy", "strategy_id"),
        "kpi_store": PgCompliance(pool, "kpi", "kpi_id"),
        "experiment_store": PgCompliance(pool, "experiment", "experiment_id"),
        "compliance_metric_store": PgCompliance(pool, "compliance_metric", "metric_id"),
        "drift_rule_store": _PgDriftRuleStoreImpl(pool),
        "drift_alert_store": _PgDriftAlertStoreImpl(pool),
        "drift_scan_store": _PgDriftScanStoreImpl(pool),
        "run_metric_store": PgCompliance(pool, "run_metric", "run_metric_id"),
        "mutation_store": PgCompliance(pool, "strategy_mutation", "mutation_id"),
        "tournament_store": PgCompliance(pool, "tournament", "tournament_id"),
        "feedback_store": PgCompliance(pool, "feedback", "feedback_id"),
        "knowledge_entry_store": PgCompliance(pool, "knowledge_entry", "entry_id"),
        "knowledge_extraction_store": PgCompliance(pool, "knowledge_extraction", "run_id"),
        "architecture_decision_store": PgCompliance(pool, "architecture_decision", "decision_id"),
        "policy_generation_store": PgCompliance(pool, "policy_generation", "run_id"),
        "guardrail_rule_store": PgCompliance(pool, "guardrail_rules", "id"),
        # Agent Action Governance stores (REQ-030)
        "governance_policy_store": PgCompliance(pool, "governance_policy", "policy_id"),
        "governance_audit_store": PgCompliance(pool, "governance_audit", "entry_id"),
        "integration_patterns": _PgIntegrationPatternStore(pool),
        "process_mining": _PgProcessMiningStore(pool),
        "workflow_definition_store": PostgresWorkflowDefinitionStore(pool),
        "codebase_index_store": _PgCodebaseIndexStore(pool),
        "attachment_store": _PgAttachmentStore(pool),
        "parsed_result_store": _PgParsedTestResultStore(pool),
        "coverage_metric_store": _PgCoverageMetricStore(pool),
        "quality_gate_rule_store": _PgQualityGateRuleStore(pool),
        "trust_score_store": _PgTrustScoreStore(pool),
        "visibility_store": _PgVisibilityStore(pool),
        "preference_store": _PgPreferenceStore(pool),
        "firewall_rule_store": _PgFirewallRuleStore(pool),
        "firewall_log_store": _PgFirewallLogStore(pool),
        "slack_notification_template_store": _PgSlackNotifTemplateStore(pool),
        "slack_notification_record_store": _PgSlackNotifRecordStore(pool),
        "agent_skill_store": _PgAgentSkillStore(pool),
        "agent_skill_binding_store": _PgAgentSkillBindingStore(pool),
        "slack_invocation_store": _PgSlackInvocationStore(pool),
        "coding_rule_store": _PgCodingRuleStore(pool),
        "violation_store": _PgRuleViolationStore(pool),
        "workflow_blueprint_store": _PgWorkflowBlueprintStore(pool),
        "sandbox_image_store": _PgSandboxImageStore(pool),
        "pooled_sandbox_store": _PgPooledSandboxStore(pool),
        "sandbox_pool_config_store": _PgSandboxPoolConfigStore(pool),
        "image_rebuild_store": _PgImageRebuildStore(pool),
        "snapshot_store": _PgSnapshotStore(pool),
        "replica_config_store": InMemoryReplicaConfigStore(),
        "sandbox_credential_store": _PgSandboxCredentialStore(pool),
        "digest_store": _PgDigestStore(pool),
        "digest_config_store": _PgDigestConfigStore(pool),
        "release_note_store": _PgReleaseNoteStore(pool),
        "channel_connection_store": _PgChannelConnectionStore(pool),
        "visual_verification_store": _PgVisualVerificationStore(pool),
        "scheduled_task_store": _PgScheduledTaskStore(pool),
        "improvement_store": PgCompliance(pool, "improvement", "improvement_id"),
        "mcp_tool_store": _PgMCPToolStore(pool),
        "mcp_tool_allowlist_store": _PgMCPToolAllowlistStore(pool),
        # Board Sync: in-memory until Postgres implementation exists
        "board_sync_config_store": BoardSyncConfigStore(),
        "external_id_mapping_store": ExternalIdMappingStore(),
    }


def wire_stores(stores: dict[str, Any], repo_provider: Any) -> None:  # noqa: ANN401
    """Wire all StoreProvider instances with their backing stores."""
    digest_store_provider.override(stores["digest_store"])
    digest_config_store_provider.override(stores["digest_config_store"])
    digest_work_item_store_provider.override(stores["work_item_store"])
    digest_pipeline_store_provider.override(stores["pipeline_store"])
    user_store_provider.override(stores["user_store"])
    release_note_store_provider.override(stores["release_note_store"])
    release_notes_repo_provider.override(repo_provider)
    team_store_provider.override(stores["team_store"])
    policy_store_provider.override(stores["policy_store"])
    notification_rule_store_provider.override(stores["notification_rule_store"])
    environment_store_provider.override(stores["environment_store"])
    variable_store_provider.override(stores["variable_store"])
    credential_store_provider.override(stores["credential_store"])
    audit_entry_store_provider.override(stores["audit_entry_store"])
    approval_request_store_provider.override(stores["approval_request_store"])
    tag_store_provider.override(stores["tag_store"])
    board_store_provider.override(stores["board_store"])
    trigger_store_provider.override(stores["trigger_store"])
    code_artifact_store_provider.override(stores["code_artifact_store"])
    artifact_content_store_provider.override(stores["artifact_content_store"])
    test_result_store_provider.override(stores["test_result_store"])
    parsed_result_store_provider.override(stores["parsed_result_store"])
    coverage_metric_store_provider.override(stores["coverage_metric_store"])
    quality_gate_rule_store_provider.override(
        stores["quality_gate_rule_store"],
    )
    artifact_pipeline_store_provider.override(stores["pipeline_store"])
    project_store_provider.override(stores["project_store"])
    work_item_store_provider.override(stores["work_item_store"])
    skill_store_provider.override(stores["skill_store"])
    agent_definition_store_provider.override(stores["agent_definition_store"])
    mcp_server_store_provider.override(stores["mcp_server_store"])
    mcp_tool_store_provider.override(stores["mcp_tool_store"])
    mcp_tool_allowlist_store_provider.override(stores["mcp_tool_allowlist_store"])
    ai_provider_store_provider.override(stores["ai_provider_store"])
    ai_providers_model_store_provider.override(stores["model_store"])
    model_store_provider.override(stores["model_store"])
    model_assignment_store_provider.override(stores["model_assignment_store"])
    models_ai_provider_store_provider.override(stores["ai_provider_store"])
    repository_store_provider.override(stores["repository_store"])
    repo_provider_provider.override(repo_provider)
    automation_store_provider.override(stores["automation_store"])
    chat_store_provider.override(stores["chat_store"])
    chat_stream_store_provider.override(stores["chat_store"])
    pipeline_store_provider.override(stores["pipeline_store"])
    regulation_store_provider.override(stores["regulation_store"])
    compliance_policy_store_provider.override(stores["compliance_policy_store"])
    procedure_store_provider.override(stores["procedure_store"])
    practice_store_provider.override(stores["practice_store"])
    strategy_store_provider.override(stores["strategy_store"])
    knowledge_entry_store_provider.override(stores["knowledge_entry_store"])
    knowledge_extraction_store_provider.override(stores["knowledge_extraction_store"])
    architecture_decision_store_provider.override(stores["architecture_decision_store"])
    policy_generation_store_provider.override(stores["policy_generation_store"])
    kpi_store_provider.override(stores["kpi_store"])
    experiment_store_provider.override(stores["experiment_store"])
    drift_rule_store_provider.override(stores["drift_rule_store"])
    drift_alert_store_provider.override(stores["drift_alert_store"])
    drift_scan_store_provider.override(stores["drift_scan_store"])
    compliance_metric_store_provider.override(stores["compliance_metric_store"])
    run_metric_store_provider.override(stores["run_metric_store"])
    mutation_store_provider.override(stores["mutation_store"])
    tournament_store_provider.override(stores["tournament_store"])
    feedback_store_provider.override(stores["feedback_store"])
    improvement_store_provider.override(stores["improvement_store"])
    codebase_index_store_provider.override(stores["codebase_index_store"])
    integration_pattern_store_provider.override(stores["integration_patterns"])
    process_mining_store_provider.override(stores["process_mining"])
    workflow_definition_store_provider.override(stores["workflow_definition_store"])
    guardrail_rule_store_provider.override(stores["guardrail_rule_store"])
    governance_policy_store_provider.override(stores["governance_policy_store"])
    governance_audit_store_provider.override(stores["governance_audit_store"])
    auth_user_store_provider.override(stores.get("auth_user_store", InMemoryAuthUserStore()))
    session_store_provider.override(stores.get("session_store", InMemorySessionStore()))
    trust_score_store_provider.override(stores["trust_score_store"])
    attachment_store_provider.override(stores["attachment_store"])
    visibility_store_provider.override(stores["visibility_store"])
    preference_store_provider.override(stores["preference_store"])
    firewall_rule_store_provider.override(stores["firewall_rule_store"])
    firewall_log_store_provider.override(stores["firewall_log_store"])
    agent_skill_store_provider.override(stores["agent_skill_store"])
    agent_skill_binding_store_provider.override(stores["agent_skill_binding_store"])
    slack_notification_template_store_provider.override(
        stores["slack_notification_template_store"],
    )
    slack_notification_record_store_provider.override(
        stores["slack_notification_record_store"],
    )
    invocation_store_provider.override(stores["slack_invocation_store"])
    coding_rule_store_provider.override(stores["coding_rule_store"])
    violation_store_provider.override(stores["violation_store"])
    blueprint_store_provider.override(stores["workflow_blueprint_store"])
    sandbox_image_store_provider.override(stores["sandbox_image_store"])
    pooled_sandbox_store_provider.override(stores["pooled_sandbox_store"])
    sandbox_pool_config_store_provider.override(stores["sandbox_pool_config_store"])
    image_rebuild_store_provider.override(stores["image_rebuild_store"])
    snapshot_store_provider.override(stores["snapshot_store"])
    connection_store_provider.override(stores["channel_connection_store"])
    verification_store_provider.override(stores["visual_verification_store"])
    sandbox_credential_store_provider.override(stores["sandbox_credential_store"])
    replica_config_store_provider.override(stores["replica_config_store"])
    scheduled_task_store_provider.override(stores["scheduled_task_store"])
    advisory_store_provider.override(stores["cve_advisory_store"])
    plan_store_provider.override(stores["remediation_plan_store"])
    result_store_provider.override(stores["remediation_result_store"])
    board_sync_config_store_provider.override(stores["board_sync_config_store"])
    board_sync_mapping_store_provider.override(stores["external_id_mapping_store"])


def wire_memory_service(memory_service: Any) -> None:  # noqa: ANN401
    """Wire the memory service provider with a concrete MemoryService instance."""
    memory_service_provider.override(memory_service)
