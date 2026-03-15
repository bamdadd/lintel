"""FastAPI application with lifespan and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import asyncpg
    from fastapi.routing import APIRoute
    from langgraph.graph.state import CompiledStateGraph

from lintel.agent_definitions_api.routes import (
    agent_definition_store_provider,
)
from lintel.agent_definitions_api.routes import (
    router as agent_definitions_router,
)
from lintel.agent_definitions_api.store import AgentDefinitionStore
from lintel.ai_providers_api.routes import (
    ai_provider_store_provider,
)
from lintel.ai_providers_api.routes import (
    model_store_provider as ai_providers_model_store_provider,
)
from lintel.ai_providers_api.routes import (
    router as ai_providers_router,
)
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.api.container import AppContainer, wire_container
from lintel.api.middleware import CorrelationMiddleware
from lintel.api.routes import (
    admin,
    approvals,
    debug,
    events,
    health,
    metrics,
    onboarding,
    pii,
    streams,
    threads,
    workflows,
)
from lintel.approval_requests_api.routes import (
    approval_request_store_provider,
)
from lintel.approval_requests_api.routes import (
    router as approval_requests_router,
)
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
from lintel.artifacts_api.routes import (
    code_artifact_store_provider,
    test_result_store_provider,
)
from lintel.artifacts_api.routes import (
    router as artifacts_router,
)
from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore
from lintel.audit_api.routes import audit_entry_store_provider
from lintel.audit_api.routes import router as audit_router
from lintel.audit_api.store import AuditEntryStore
from lintel.automations_api.routes import (
    InMemoryAutomationStore,
    automation_store_provider,
)
from lintel.automations_api.routes import (
    router as automations_router,
)
from lintel.boards.routes import (
    board_store_provider,
    tag_store_provider,
)
from lintel.boards.routes import (
    router as boards_router,
)
from lintel.boards.store import BoardStore, TagStore
from lintel.chat_api.routes import ChatStore, chat_store_provider
from lintel.chat_api.routes import router as chat_router_routes
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
from lintel.compliance_api.routes import (
    router as compliance_router,
)
from lintel.compliance_api.store import ComplianceStore
from lintel.credentials_api.routes import (
    credential_store_provider,
)
from lintel.credentials_api.routes import (
    router as credentials_router,
)
from lintel.credentials_api.store import InMemoryCredentialStore
from lintel.environments_api.routes import (
    environment_store_provider,
)
from lintel.environments_api.routes import (
    router as environments_router,
)
from lintel.environments_api.store import InMemoryEnvironmentStore
from lintel.event_bus.in_memory import InMemoryEventBus
from lintel.event_store.in_memory import InMemoryEventStore
from lintel.experimentation_api.routes import (
    compliance_metric_store_provider,
    experiment_store_provider,
    kpi_store_provider,
)
from lintel.experimentation_api.routes import (
    router as experimentation_router,
)
from lintel.mcp_servers_api.routes import (
    mcp_server_store_provider,
)
from lintel.mcp_servers_api.routes import (
    router as mcp_servers_router,
)
from lintel.mcp_servers_api.store import InMemoryMCPServerStore
from lintel.models_api.routes import (
    ai_provider_store_provider as models_ai_provider_store_provider,
)
from lintel.models_api.routes import (
    model_assignment_store_provider,
    model_store_provider,
)
from lintel.models_api.routes import (
    router as models_router,
)
from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore
from lintel.notifications_api.routes import (
    notification_rule_store_provider,
)
from lintel.notifications_api.routes import (
    router as notifications_router,
)
from lintel.notifications_api.store import NotificationRuleStore
from lintel.pipelines_api.routes import (
    InMemoryPipelineStore,
    pipeline_store_provider,
)
from lintel.pipelines_api.routes import (
    router as pipelines_router,
)
from lintel.policies_api.routes import policy_store_provider
from lintel.policies_api.routes import router as policies_router
from lintel.policies_api.store import InMemoryPolicyStore
from lintel.projections.audit import AuditProjection
from lintel.projections.engine import InMemoryProjectionEngine
from lintel.projections.quality_metrics import QualityMetricsProjection
from lintel.projections.task_backlog import TaskBacklogProjection
from lintel.projections.thread_status import ThreadStatusProjection
from lintel.projects_api.routes import project_store_provider
from lintel.projects_api.routes import router as projects_router
from lintel.projects_api.store import ProjectStore
from lintel.repos.github_provider import GitHubRepoProvider
from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repositories_api.routes import (
    repo_provider_provider,
    repository_store_provider,
)
from lintel.repositories_api.routes import (
    router as repositories_router,
)
from lintel.sandbox.docker_backend import DockerSandboxManager
from lintel.sandboxes_api.routes import SandboxStore
from lintel.sandboxes_api.routes import router as sandboxes_router
from lintel.settings_api.routes import router as settings_router
from lintel.skills_api.routes import router as skills_router
from lintel.skills_api.routes import skill_store_provider
from lintel.skills_api.store import InMemorySkillStore
from lintel.teams.routes import router as teams_router
from lintel.teams.routes import team_store_provider
from lintel.teams.store import InMemoryTeamStore
from lintel.triggers_api.routes import router as triggers_router
from lintel.triggers_api.routes import trigger_store_provider
from lintel.triggers_api.store import InMemoryTriggerStore
from lintel.users.routes import router as users_router
from lintel.users.routes import user_store_provider
from lintel.users.store import InMemoryUserStore
from lintel.variables_api.routes import router as variables_router
from lintel.variables_api.routes import variable_store_provider
from lintel.variables_api.store import InMemoryVariableStore
from lintel.work_items_api.routes import (
    router as work_items_router,
)
from lintel.work_items_api.routes import (
    work_item_store_provider,
)
from lintel.work_items_api.store import WorkItemStore
from lintel.workflow_definitions_api.routes import router as workflow_definitions_router


async def _seed_defaults(stores: dict[str, Any]) -> None:
    """Seed built-in agent definitions and skills into stores."""
    import dataclasses

    from lintel.api.domain.seed import DEFAULT_AGENTS, DEFAULT_SKILLS

    agent_store = stores["agent_definition_store"]
    for agent in DEFAULT_AGENTS:
        data = dataclasses.asdict(agent)
        # Convert tuples/frozensets to lists for JSON compat
        for key, value in data.items():
            if isinstance(value, (frozenset, tuple)):
                data[key] = list(value)
        # max_tokens and temperature are agent-level tuning params
        # model selection comes from the user's configured AI providers
        existing = await agent_store.get(agent.agent_id)
        if existing is None:
            await agent_store.create(data)

    skill_store = stores["skill_store"]
    for skill in DEFAULT_SKILLS:
        # Always upsert builtins to refresh description, roles, schemas
        await skill_store.register(
            skill_id=skill.skill_id,
            version=skill.version,
            name=skill.name,
            input_schema=skill.input_schema or {},
            output_schema=skill.output_schema or {},
            execution_mode=skill.execution_mode.value,
            description=skill.description,
            allowed_agent_roles=skill.allowed_agent_roles,
        )
        # In-memory store: also set extended metadata
        if hasattr(skill_store, "_metadata"):
            skill_store._metadata[skill.skill_id] = {
                "description": skill.description,
                "content": skill.system_prompt,
                "category": skill.category.value,
                "tags": list(skill.tags),
                "allowed_agent_roles": list(skill.allowed_agent_roles),
                "is_builtin": skill.is_builtin,
                "enabled": skill.enabled,
            }


def _create_in_memory_stores() -> dict[str, Any]:
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


def _dc_to_dict(obj: Any) -> dict[str, Any]:  # noqa: ANN401
    """Convert a frozen dataclass to a dict, handling nested tuples."""
    from dataclasses import asdict

    d = asdict(obj)
    # Convert tuples to lists for JSON serialization compatibility
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d


def _create_postgres_stores(pool: asyncpg.Pool) -> dict[str, Any]:
    """Create all Postgres-backed stores."""
    from lintel.event_store.postgres import PostgresEventStore
    from lintel.persistence.dict_store import (
        PostgresComplianceStore as PgCompliance,
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
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Configure structured logging so structlog output appears in console
    from lintel.observability.logging import configure_logging

    log_level = os.environ.get("LINTEL_LOG_LEVEL", "INFO").upper()
    configure_logging(log_level=log_level, log_format="console")

    # Configure OpenTelemetry tracing and metrics
    from lintel.observability.metrics import configure_metrics
    from lintel.observability.tracing import configure_tracing

    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    configure_tracing(otel_endpoint=otel_endpoint)
    configure_metrics()

    # Determine storage backend from LINTEL_STORAGE_BACKEND setting.
    # Values: "postgres" (requires LINTEL_DB_DSN), "memory" (default).
    storage_backend = os.environ.get("LINTEL_STORAGE_BACKEND", "").lower()
    dsn = os.environ.get("LINTEL_DB_DSN")
    db_pool = None

    # Auto-detect: if backend not set explicitly, infer from DSN presence
    if not storage_backend:
        storage_backend = "postgres" if dsn else "memory"

    if storage_backend == "postgres":
        if not dsn:
            msg = "LINTEL_STORAGE_BACKEND=postgres requires LINTEL_DB_DSN to be set"
            raise RuntimeError(msg)
        import asyncpg

        db_pool = await asyncpg.create_pool(dsn)  # type: ignore[no-untyped-call]
        stores = _create_postgres_stores(cast("asyncpg.Pool", db_pool))
    else:
        stores = _create_in_memory_stores()

    # Assign all stores to app state
    for name, store in stores.items():
        setattr(app.state, name, store)

    # Wire command dispatcher
    from lintel.api.domain.command_dispatcher import InMemoryCommandDispatcher
    from lintel.chat_api.chat_router import ChatRouter
    from lintel.models.router import DefaultModelRouter
    from lintel.workflows.workflow_executor import WorkflowExecutor

    dispatcher = InMemoryCommandDispatcher()
    event_store = stores["event_store"]

    # Wire chat router with model router and MCP tool support
    ollama_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    model_router = DefaultModelRouter(
        ollama_api_base=ollama_base,
        model_store=stores["model_store"],
        ai_provider_store=stores["ai_provider_store"],
        model_assignment_store=stores["model_assignment_store"],
    )

    from lintel.agents.runtime import AgentRuntime
    from lintel.infrastructure.mcp.tool_client import MCPToolClient

    mcp_tool_client = MCPToolClient()
    agent_runtime = AgentRuntime(
        event_store=event_store,
        model_router=model_router,
        mcp_tool_client=mcp_tool_client,
        mcp_server_store=stores["mcp_server_store"],
    )
    app.state.agent_runtime = agent_runtime
    app.state.model_router = model_router

    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()

    def _graph_factory(workflow_type: str) -> CompiledStateGraph:  # type: ignore[type-arg]
        """Build and compile a LangGraph with interrupt support."""
        from lintel.workflows.registry import get_workflow_builder

        builder_fn = get_workflow_builder(workflow_type)
        state_graph = builder_fn()

        # Collect approval gate nodes for interrupt_before
        approval_nodes = [name for name in state_graph.nodes if "approval_gate" in name]

        return state_graph.compile(
            checkpointer=_checkpointer,
            interrupt_before=approval_nodes or None,
        )

    from lintel.observability.step_metrics import OtelStepMetricsRecorder

    executor = WorkflowExecutor(
        event_store=event_store,
        graph_factory=_graph_factory,
        agent_runtime=agent_runtime,
        app_state=app.state,
        step_metrics=OtelStepMetricsRecorder(),
    )

    app.state.workflow_executor = executor

    from lintel.workflows.commands import StartWorkflow

    dispatcher.register(StartWorkflow, executor.execute)
    app.state.command_dispatcher = dispatcher

    chat_router = ChatRouter(
        model_router=model_router,
        mcp_tool_client=mcp_tool_client,
        mcp_server_store=stores["mcp_server_store"],
    )
    app.state.chat_router = chat_router
    app.state.mcp_tool_client = mcp_tool_client

    # Seed built-in agents and skills
    await _seed_defaults(stores)

    # Initialize event bus and projections
    event_bus = InMemoryEventBus()
    app.state.event_bus = event_bus

    # Wire event bus into the event store so events are published after persist
    event_store.set_event_bus(event_bus)

    thread_status = ThreadStatusProjection()
    task_backlog = TaskBacklogProjection()
    audit_projection = AuditProjection(stores["audit_entry_store"])
    quality_metrics = QualityMetricsProjection()
    engine = InMemoryProjectionEngine(event_bus=event_bus)
    await engine.register(thread_status)
    await engine.register(task_backlog)
    await engine.register(audit_projection)
    await engine.register(quality_metrics)
    await engine.start()

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.quality_metrics_projection = quality_metrics
    app.state.projection_engine = engine
    sandbox_manager = DockerSandboxManager()
    app.state.sandbox_manager = sandbox_manager

    # Re-attach to any surviving Docker containers from previous runs
    try:
        recovered = await sandbox_manager.recover_containers()
        if recovered:
            import logging

            logger = logging.getLogger("lintel")
            logger.info("Recovered %d sandbox containers", len(recovered))
            store = app.state.sandbox_store
            for meta in recovered:
                try:
                    await store.add(meta["sandbox_id"], meta)
                except Exception:
                    logger.warning("Failed to restore metadata for %s", meta["sandbox_id"])
    except Exception:
        pass  # Docker may not be available

    # Construct repo provider for GitHub API access (commits, PRs, branches)
    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo_provider = GitHubRepoProvider(token=github_token) if github_token else None

    # Wire DI container so route handlers can use Provide[AppContainer.X]
    container = AppContainer()
    services = {
        "event_bus": event_bus,
        "model_router": model_router,
        "chat_router": chat_router,
        "agent_runtime": agent_runtime,
        "command_dispatcher": dispatcher,
        "workflow_executor": executor,
        "sandbox_manager": sandbox_manager,
        "mcp_tool_client": mcp_tool_client,
        "repo_provider": repo_provider,
        "projection_engine": engine,
        "thread_status_projection": thread_status,
        "quality_metrics_projection": quality_metrics,
        "task_backlog_projection": task_backlog,
    }
    wire_container(container, stores, services)
    container.wire(
        packages=["lintel.api.routes"],
        modules=["lintel.api.deps"],
    )
    user_store_provider.override(stores["user_store"])
    team_store_provider.override(stores["team_store"])
    policy_store_provider.override(stores["policy_store"])
    notification_rule_store_provider.override(stores["notification_rule_store"])
    environment_store_provider.override(stores["environment_store"])
    variable_store_provider.override(stores["variable_store"])
    credential_store_provider.override(stores["credential_store"])
    audit_entry_store_provider.override(stores["audit_entry_store"])
    approval_request_store_provider.override(stores["approval_request_store"])
    boards_tag_provider_ref = tag_store_provider
    boards_tag_provider_ref.override(stores["tag_store"])
    boards_board_provider_ref = board_store_provider
    boards_board_provider_ref.override(stores["board_store"])
    trigger_store_provider.override(stores["trigger_store"])
    code_artifact_store_provider.override(stores["code_artifact_store"])
    test_result_store_provider.override(stores["test_result_store"])
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
    # New extracted packages
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
    app.state.container = container

    # Start automation scheduler
    import asyncio

    from lintel.automations_api.scheduler import AutomationScheduler

    async def _fire_automation(
        auto: Any,  # noqa: ANN401
        metadata: dict[str, Any],
    ) -> str:
        """Create a PipelineRun and emit AutomationFired event."""
        from uuid import uuid4

        from lintel.domain.events import AutomationFired
        from lintel.workflows.types import PipelineRun

        run_id = str(uuid4())
        pipeline_run = PipelineRun(
            run_id=run_id,
            project_id=auto.project_id,
            work_item_id="",
            workflow_definition_id=auto.trigger_config.get("workflow_definition_id", ""),
            trigger_type=f"automation:{auto.automation_id}",
        )
        await stores["pipeline_store"].add(pipeline_run)
        event = AutomationFired(
            payload={
                "resource_id": auto.automation_id,
                "pipeline_run_id": run_id,
                "trigger_type": metadata.get("trigger", "unknown"),
            },
        )
        await event_bus.publish(event)
        return run_id

    automation_scheduler = AutomationScheduler(
        automation_store=stores["automation_store"],
        fire_fn=_fire_automation,
    )

    # Subscribe event-triggered automations to EventBus
    all_automations = await stores["automation_store"].list_all()

    async def _on_event(event: Any) -> None:  # noqa: ANN401
        await automation_scheduler.handle_event(event)

    event_types: set[str] = set()
    for auto in all_automations:
        if auto.trigger_type == "event" and auto.enabled:
            for et in auto.trigger_config.get("event_types", []):
                event_types.add(et)
    if event_types:
        await event_bus.subscribe(
            frozenset(event_types),
            type("_AutoEventHandler", (), {"handle": staticmethod(_on_event)})(),
        )

    # Subscribe to pipeline completion for queue dequeue
    async def _on_pipeline_complete(event: Any) -> None:  # noqa: ANN401
        payload = event.payload or {}
        run_id = payload.get("resource_id", "")
        trigger = payload.get("trigger_type", "")
        if trigger.startswith("automation:"):
            aid = trigger.split(":", 1)[1]
            await automation_scheduler.mark_run_completed(aid, run_id)

    await event_bus.subscribe(
        frozenset({"PipelineRunCompleted", "PipelineRunFailed"}),
        type("_PipelineCompleteHandler", (), {"handle": staticmethod(_on_pipeline_complete)})(),
    )

    background_tasks: set[asyncio.Task[Any]] = set()
    app.state._background_tasks = background_tasks
    scheduler_task = asyncio.create_task(automation_scheduler.run())
    app.state._background_tasks.add(scheduler_task)
    scheduler_task.add_done_callback(app.state._background_tasks.discard)

    yield

    container.unwire()
    # Cleanup
    scheduler_task.cancel()
    await engine.stop()
    if db_pool is not None:
        await db_pool.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    def _generate_unique_id(route: APIRoute) -> str:
        if route.tags:
            return f"{route.tags[0]}_{route.name}"
        return route.name

    app = FastAPI(
        title="Lintel",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=_generate_unique_id,
    )
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(threads.router, prefix="/api/v1", tags=["threads"])
    app.include_router(repositories_router, prefix="/api/v1", tags=["repositories"])
    app.include_router(workflows.router, prefix="/api/v1", tags=["workflows"])
    app.include_router(agent_definitions_router, prefix="/api/v1", tags=["agents"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["approvals"])
    app.include_router(sandboxes_router, prefix="/api/v1", tags=["sandboxes"])
    app.include_router(skills_router, prefix="/api/v1", tags=["skills"])
    app.include_router(streams.router, prefix="/api/v1", tags=["streams"])
    app.include_router(events.router, prefix="/api/v1", tags=["events"])
    app.include_router(pii.router, prefix="/api/v1", tags=["pii"])
    app.include_router(settings_router, prefix="/api/v1", tags=["settings"])
    app.include_router(workflow_definitions_router, prefix="/api/v1", tags=["workflow-definitions"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
    app.include_router(credentials_router, prefix="/api/v1", tags=["credentials"])
    app.include_router(ai_providers_router, prefix="/api/v1", tags=["ai-providers"])
    app.include_router(projects_router, prefix="/api/v1", tags=["projects"])
    app.include_router(work_items_router, prefix="/api/v1", tags=["work-items"])
    app.include_router(pipelines_router, prefix="/api/v1", tags=["pipelines"])
    app.include_router(environments_router, prefix="/api/v1", tags=["environments"])
    app.include_router(triggers_router, prefix="/api/v1", tags=["triggers"])
    app.include_router(automations_router, prefix="/api/v1", tags=["automations"])
    app.include_router(variables_router, prefix="/api/v1", tags=["variables"])
    app.include_router(users_router, prefix="/api/v1", tags=["users"])
    app.include_router(teams_router, prefix="/api/v1", tags=["teams"])
    app.include_router(policies_router, prefix="/api/v1", tags=["policies"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["notifications"])
    app.include_router(audit_router, prefix="/api/v1", tags=["audit"])
    app.include_router(artifacts_router, prefix="/api/v1", tags=["artifacts"])
    app.include_router(approval_requests_router, prefix="/api/v1", tags=["approval-requests"])
    app.include_router(chat_router_routes, prefix="/api/v1", tags=["chat"])
    app.include_router(models_router, prefix="/api/v1", tags=["models"])
    app.include_router(mcp_servers_router, prefix="/api/v1", tags=["mcp-servers"])
    app.include_router(onboarding.router, prefix="/api/v1", tags=["onboarding"])
    app.include_router(boards_router, prefix="/api/v1", tags=["boards"])
    app.include_router(compliance_router, prefix="/api/v1", tags=["compliance"])
    app.include_router(experimentation_router, prefix="/api/v1", tags=["experimentation"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(debug.router, prefix="/api/v1", tags=["debug"])

    # Expose all API endpoints as MCP tools/resources
    from fastapi_mcp import FastApiMCP  # type: ignore[import-untyped]

    mcp = FastApiMCP(
        app,
        name="Lintel MCP",
        describe_all_responses=True,
    )
    mcp.mount_http()

    # Serve SPA static files in production (must be last)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")

    return app


app = create_app()
