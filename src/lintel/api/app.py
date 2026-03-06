"""FastAPI application with lifespan and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
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
    metrics,
    notifications,
    pii,
    pipelines,
    policies,
    projects,
    repositories,
    sandboxes,
    settings,
    skills,
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
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore
from lintel.infrastructure.sandbox.docker_backend import DockerSandboxManager

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Initialize projections
    thread_status = ThreadStatusProjection()
    task_backlog = TaskBacklogProjection()
    engine = InMemoryProjectionEngine()
    await engine.register(thread_status)
    await engine.register(task_backlog)

    repository_store = InMemoryRepositoryStore()
    skill_store = InMemorySkillStore()
    credential_store = InMemoryCredentialStore()
    ai_provider_store = InMemoryAIProviderStore()

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.projection_engine = engine
    app.state.repository_store = repository_store
    app.state.skill_store = skill_store
    app.state.credential_store = credential_store
    app.state.ai_provider_store = ai_provider_store
    app.state.project_store = ProjectStore()
    app.state.work_item_store = WorkItemStore()
    app.state.pipeline_store = InMemoryPipelineStore()
    app.state.environment_store = InMemoryEnvironmentStore()
    app.state.trigger_store = InMemoryTriggerStore()
    app.state.variable_store = InMemoryVariableStore()
    app.state.user_store = InMemoryUserStore()
    app.state.team_store = InMemoryTeamStore()
    app.state.policy_store = InMemoryPolicyStore()
    app.state.notification_rule_store = NotificationRuleStore()
    app.state.audit_entry_store = AuditEntryStore()
    app.state.code_artifact_store = CodeArtifactStore()
    app.state.test_result_store = TestResultStore()
    app.state.approval_request_store = InMemoryApprovalRequestStore()
    app.state.chat_store = ChatStore()
    app.state.agent_definition_store = AgentDefinitionStore()
    app.state.sandbox_manager = DockerSandboxManager()

    yield
    # Cleanup


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
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    return app


app = create_app()
