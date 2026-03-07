"""FastAPI application with lifespan and dependency injection."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import asyncpg
    from fastapi.routing import APIRoute

from lintel.api.middleware import CorrelationMiddleware
from lintel.api.routes import (
    admin,
    agents,
    ai_providers,
    approval_requests,
    approvals,
    artifacts,
    audit,
    chat,
    credentials,
    environments,
    events,
    health,
    mcp_servers,
    metrics,
    models,
    notifications,
    onboarding,
    pii,
    pipelines,
    policies,
    projects,
    repositories,
    sandboxes,
    settings,
    skills,
    streams,
    teams,
    threads,
    triggers,
    users,
    variables,
    work_items,
    workflow_definitions,
    workflows,
)
from lintel.api.routes.agents import AgentDefinitionStore
from lintel.api.routes.ai_providers import InMemoryAIProviderStore
from lintel.api.routes.approval_requests import InMemoryApprovalRequestStore
from lintel.api.routes.artifacts import CodeArtifactStore, TestResultStore
from lintel.api.routes.audit import AuditEntryStore
from lintel.api.routes.chat import ChatStore
from lintel.api.routes.credentials import InMemoryCredentialStore
from lintel.api.routes.environments import InMemoryEnvironmentStore
from lintel.api.routes.mcp_servers import InMemoryMCPServerStore
from lintel.api.routes.models import InMemoryModelAssignmentStore, InMemoryModelStore
from lintel.api.routes.notifications import NotificationRuleStore
from lintel.api.routes.pipelines import InMemoryPipelineStore
from lintel.api.routes.policies import InMemoryPolicyStore
from lintel.api.routes.projects import ProjectStore
from lintel.api.routes.skills import InMemorySkillStore
from lintel.api.routes.teams import InMemoryTeamStore
from lintel.api.routes.triggers import InMemoryTriggerStore
from lintel.api.routes.users import InMemoryUserStore
from lintel.api.routes.variables import InMemoryVariableStore
from lintel.api.routes.work_items import WorkItemStore
from lintel.infrastructure.event_store.in_memory import InMemoryEventStore
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore
from lintel.infrastructure.sandbox.docker_backend import DockerSandboxManager


async def _seed_defaults(stores: dict[str, Any]) -> None:
    """Seed built-in agent definitions and skills into stores."""
    import dataclasses

    from lintel.domain.seed import DEFAULT_AGENTS, DEFAULT_SKILLS

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
    existing_skills = await skill_store.list_skills()
    for skill in DEFAULT_SKILLS:
        if skill.skill_id not in existing_skills:
            await skill_store.register(
                skill_id=skill.skill_id,
                version=skill.version,
                name=skill.name,
                input_schema=skill.input_schema or {},
                output_schema=skill.output_schema or {},
                execution_mode=skill.execution_mode.value,
            )
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
    }


def _create_postgres_stores(pool: asyncpg.Pool) -> dict[str, Any]:
    """Create all Postgres-backed stores."""
    from lintel.infrastructure.event_store.postgres import PostgresEventStore
    from lintel.infrastructure.persistence.stores import (
        PostgresAgentDefinitionStore,
        PostgresAIProviderStore,
        PostgresApprovalRequestStore,
        PostgresAuditEntryStore,
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
        PostgresSkillStore,
        PostgresTeamStore,
        PostgresTestResultStore,
        PostgresTriggerStore,
        PostgresUserStore,
        PostgresVariableStore,
        PostgresWorkItemStore,
    )

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
    }


async def _noop_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
    """Placeholder graph stream that yields nothing. Replaced by GraphCompiler."""
    return
    yield  # Make this an async generator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Configure structured logging so structlog output appears in console
    from lintel.infrastructure.observability.logging import configure_logging

    log_level = os.environ.get("LINTEL_LOG_LEVEL", "INFO").upper()
    configure_logging(log_level=log_level, log_format="console")

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
    from lintel.domain.chat_router import ChatRouter
    from lintel.domain.command_dispatcher import InMemoryCommandDispatcher
    from lintel.domain.workflow_executor import WorkflowExecutor
    from lintel.infrastructure.models.router import DefaultModelRouter

    dispatcher = InMemoryCommandDispatcher()
    event_store = stores["event_store"]

    # Create a no-op graph for now (will be replaced by GraphCompiler in Phase 2)
    from unittest.mock import AsyncMock

    noop_graph = AsyncMock()
    noop_graph.astream = _noop_astream

    # Wire chat router with model router and MCP tool support
    ollama_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    model_router = DefaultModelRouter(ollama_api_base=ollama_base)

    from lintel.agents.runtime import AgentRuntime

    agent_runtime = AgentRuntime(event_store=event_store, model_router=model_router)
    app.state.agent_runtime = agent_runtime

    executor = WorkflowExecutor(
        event_store=event_store,
        graph=noop_graph,
        agent_runtime=agent_runtime,
    )

    from lintel.contracts.commands import StartWorkflow

    dispatcher.register(StartWorkflow, executor.execute)
    app.state.command_dispatcher = dispatcher

    from lintel.infrastructure.mcp.tool_client import MCPToolClient

    mcp_tool_client = MCPToolClient()
    chat_router = ChatRouter(
        model_router=model_router,
        mcp_tool_client=mcp_tool_client,
        mcp_server_store=stores["mcp_server_store"],
    )
    app.state.chat_router = chat_router
    app.state.mcp_tool_client = mcp_tool_client

    # Seed built-in agents and skills
    await _seed_defaults(stores)

    # Initialize projections
    thread_status = ThreadStatusProjection()
    task_backlog = TaskBacklogProjection()
    engine = InMemoryProjectionEngine()
    await engine.register(thread_status)
    await engine.register(task_backlog)

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.projection_engine = engine
    app.state.sandbox_manager = DockerSandboxManager()

    yield
    # Cleanup
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
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(threads.router, prefix="/api/v1", tags=["threads"])
    app.include_router(repositories.router, prefix="/api/v1", tags=["repositories"])
    app.include_router(workflows.router, prefix="/api/v1", tags=["workflows"])
    app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["approvals"])
    app.include_router(sandboxes.router, prefix="/api/v1", tags=["sandboxes"])
    app.include_router(skills.router, prefix="/api/v1", tags=["skills"])
    app.include_router(streams.router, prefix="/api/v1", tags=["streams"])
    app.include_router(events.router, prefix="/api/v1", tags=["events"])
    app.include_router(pii.router, prefix="/api/v1", tags=["pii"])
    app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
    app.include_router(workflow_definitions.router, prefix="/api/v1", tags=["workflow-definitions"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
    app.include_router(credentials.router, prefix="/api/v1", tags=["credentials"])
    app.include_router(ai_providers.router, prefix="/api/v1", tags=["ai-providers"])
    app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
    app.include_router(work_items.router, prefix="/api/v1", tags=["work-items"])
    app.include_router(pipelines.router, prefix="/api/v1", tags=["pipelines"])
    app.include_router(environments.router, prefix="/api/v1", tags=["environments"])
    app.include_router(triggers.router, prefix="/api/v1", tags=["triggers"])
    app.include_router(variables.router, prefix="/api/v1", tags=["variables"])
    app.include_router(users.router, prefix="/api/v1", tags=["users"])
    app.include_router(teams.router, prefix="/api/v1", tags=["teams"])
    app.include_router(policies.router, prefix="/api/v1", tags=["policies"])
    app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
    app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
    app.include_router(artifacts.router, prefix="/api/v1", tags=["artifacts"])
    app.include_router(approval_requests.router, prefix="/api/v1", tags=["approval-requests"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(models.router, prefix="/api/v1", tags=["models"])
    app.include_router(mcp_servers.router, prefix="/api/v1", tags=["mcp-servers"])
    app.include_router(onboarding.router, prefix="/api/v1", tags=["onboarding"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])

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
