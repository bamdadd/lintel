"""Store factory functions and StoreProvider wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

from lintel.agent_definitions_api.routes import agent_definition_store_provider
from lintel.agent_definitions_api.store import AgentDefinitionStore
from lintel.ai_providers_api.routes import ai_provider_store_provider
from lintel.ai_providers_api.routes import model_store_provider as ai_providers_model_store_provider
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.approval_requests_api.routes import approval_request_store_provider
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
from lintel.artifacts_api.routes import (
    code_artifact_store_provider,
    test_result_store_provider,
)
from lintel.artifacts_api.routes import (
    pipeline_store_provider as artifact_pipeline_store_provider,
)
from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore
from lintel.audit_api.routes import audit_entry_store_provider
from lintel.audit_api.store import AuditEntryStore
from lintel.automations_api.routes import InMemoryAutomationStore, automation_store_provider
from lintel.boards.routes import board_store_provider, tag_store_provider
from lintel.boards.store import BoardStore, TagStore
from lintel.chat_api.routes import ChatStore, chat_store_provider
from lintel.compliance_api.routes import (
    architecture_decision_store_provider,
    compliance_policy_store_provider,
    knowledge_entry_store_provider,
    knowledge_extraction_store_provider,
    practice_store_provider,
    procedure_store_provider,
    regulation_store_provider,
    strategy_store_provider,
)
from lintel.compliance_api.store import ComplianceStore
from lintel.credentials_api.routes import credential_store_provider
from lintel.credentials_api.store import InMemoryCredentialStore
from lintel.environments_api.routes import environment_store_provider
from lintel.environments_api.store import InMemoryEnvironmentStore
from lintel.event_store.in_memory import InMemoryEventStore
from lintel.experimentation_api.routes import (
    compliance_metric_store_provider,
    experiment_store_provider,
    kpi_store_provider,
)
from lintel.integration_patterns_api.routes import integration_pattern_store_provider
from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore
from lintel.mcp_servers_api.routes import mcp_server_store_provider
from lintel.mcp_servers_api.store import InMemoryMCPServerStore
from lintel.memory_api.dependencies import memory_service_provider
from lintel.models_api.routes import ai_provider_store_provider as models_ai_provider_store_provider
from lintel.models_api.routes import model_assignment_store_provider, model_store_provider
from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore
from lintel.notifications_api.routes import notification_rule_store_provider
from lintel.notifications_api.store import NotificationRuleStore
from lintel.pipelines_api.routes import InMemoryPipelineStore, pipeline_store_provider
from lintel.policies_api.routes import policy_store_provider
from lintel.policies_api.store import InMemoryPolicyStore
from lintel.projects_api.routes import project_store_provider
from lintel.projects_api.store import ProjectStore
from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repositories_api.routes import repo_provider_provider, repository_store_provider
from lintel.sandboxes_api.routes import SandboxStore
from lintel.skills_api.routes import skill_store_provider
from lintel.skills_api.store import InMemorySkillStore
from lintel.teams.routes import team_store_provider
from lintel.teams.store import InMemoryTeamStore
from lintel.triggers_api.routes import trigger_store_provider
from lintel.triggers_api.store import InMemoryTriggerStore
from lintel.users.routes import user_store_provider
from lintel.users.store import InMemoryUserStore
from lintel.variables_api.routes import variable_store_provider
from lintel.variables_api.store import InMemoryVariableStore
from lintel.work_items_api.routes import work_item_store_provider
from lintel.work_items_api.store import WorkItemStore
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
        "user_store": InMemoryUserStore(),
        "team_store": InMemoryTeamStore(),
        "policy_store": InMemoryPolicyStore(),
        "notification_rule_store": NotificationRuleStore(),
        "audit_entry_store": AuditEntryStore(),
        "code_artifact_store": CodeArtifactStore(),
        "test_result_store": TestResultStore(),
        "approval_request_store": InMemoryApprovalRequestStore(),
        "chat_store": ChatStore(),
        "agent_definition_store": AgentDefinitionStore(),
        "model_store": InMemoryModelStore(),
        "model_assignment_store": InMemoryModelAssignmentStore(),
        "mcp_server_store": InMemoryMCPServerStore(),
        "sandbox_store": SandboxStore(),
        "tag_store": TagStore(),
        "board_store": BoardStore(),
        "integration_patterns": InMemoryIntegrationPatternStore(),
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
        "knowledge_entry_store": ComplianceStore("entry_id"),
        "knowledge_extraction_store": ComplianceStore("run_id"),
        "architecture_decision_store": ComplianceStore("decision_id"),
    }


def create_postgres_stores(pool: asyncpg.Pool) -> dict[str, Any]:
    """Create all Postgres-backed stores."""
    from lintel.event_store.postgres import PostgresEventStore
    from lintel.integration_patterns_api.postgres_store import (
        PostgresIntegrationPatternStore as _PgIntegrationPatternStore,
    )
    from lintel.persistence.dict_store import PostgresComplianceStore as PgCompliance
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
    from lintel.workflow_definitions_api.store import PostgresWorkflowDefinitionStore

    class _BoardStoreAdapter:
        """Adapt PostgresCrudStore (dataclass) to dict-based interface used by routes."""

        def __init__(self, pg: _PgBoardStore) -> None:
            self._pg = pg

        async def add(self, data: dict[str, Any]) -> None:
            from lintel.domain.types import Board, BoardColumn

            cols = tuple(BoardColumn(**c) for c in data.get("columns", []))
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

            cols = tuple(BoardColumn(**c) for c in data.get("columns", []))
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
        "knowledge_entry_store": PgCompliance(pool, "knowledge_entry", "entry_id"),
        "knowledge_extraction_store": PgCompliance(pool, "knowledge_extraction", "run_id"),
        "architecture_decision_store": PgCompliance(pool, "architecture_decision", "decision_id"),
        "integration_patterns": _PgIntegrationPatternStore(pool),
        "workflow_definition_store": PostgresWorkflowDefinitionStore(pool),
    }


def wire_stores(stores: dict[str, Any], repo_provider: Any) -> None:  # noqa: ANN401
    """Wire all StoreProvider instances with their backing stores."""
    user_store_provider.override(stores["user_store"])
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
    test_result_store_provider.override(stores["test_result_store"])
    artifact_pipeline_store_provider.override(stores["pipeline_store"])
    project_store_provider.override(stores["project_store"])
    work_item_store_provider.override(stores["work_item_store"])
    skill_store_provider.override(stores["skill_store"])
    agent_definition_store_provider.override(stores["agent_definition_store"])
    mcp_server_store_provider.override(stores["mcp_server_store"])
    ai_provider_store_provider.override(stores["ai_provider_store"])
    ai_providers_model_store_provider.override(stores["model_store"])
    model_store_provider.override(stores["model_store"])
    model_assignment_store_provider.override(stores["model_assignment_store"])
    models_ai_provider_store_provider.override(stores["ai_provider_store"])
    repository_store_provider.override(stores["repository_store"])
    repo_provider_provider.override(repo_provider)
    automation_store_provider.override(stores["automation_store"])
    chat_store_provider.override(stores["chat_store"])
    pipeline_store_provider.override(stores["pipeline_store"])
    regulation_store_provider.override(stores["regulation_store"])
    compliance_policy_store_provider.override(stores["compliance_policy_store"])
    procedure_store_provider.override(stores["procedure_store"])
    practice_store_provider.override(stores["practice_store"])
    strategy_store_provider.override(stores["strategy_store"])
    knowledge_entry_store_provider.override(stores["knowledge_entry_store"])
    knowledge_extraction_store_provider.override(stores["knowledge_extraction_store"])
    architecture_decision_store_provider.override(stores["architecture_decision_store"])
    kpi_store_provider.override(stores["kpi_store"])
    experiment_store_provider.override(stores["experiment_store"])
    compliance_metric_store_provider.override(stores["compliance_metric_store"])
    integration_pattern_store_provider.override(stores["integration_patterns"])
    workflow_definition_store_provider.override(stores["workflow_definition_store"])


def wire_memory_service(memory_service: Any) -> None:  # noqa: ANN401
    """Wire the memory service provider with a concrete MemoryService instance."""
    memory_service_provider.override(memory_service)
