"""Router registration — mounts all API routers onto the FastAPI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.agent_definitions_api.routes import router as agent_definitions_router
from lintel.ai_providers_api.routes import router as ai_providers_router
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
from lintel.approval_requests_api.routes import router as approval_requests_router
from lintel.artifacts_api.routes import router as artifacts_router
from lintel.audit_api.routes import router as audit_router
from lintel.automations_api.routes import router as automations_router
from lintel.boards.routes import router as boards_router
from lintel.chat_api.routes import router as chat_router_routes
from lintel.compliance_api.routes import router as compliance_router
from lintel.credentials_api.routes import router as credentials_router
from lintel.environments_api.routes import router as environments_router
from lintel.experimentation_api.routes import router as experimentation_router
from lintel.mcp_servers_api.routes import router as mcp_servers_router
from lintel.models_api.routes import router as models_router
from lintel.notifications_api.routes import router as notifications_router
from lintel.pipelines_api.routes import router as pipelines_router
from lintel.policies_api.routes import router as policies_router
from lintel.projects_api.routes import router as projects_router
from lintel.repositories_api.routes import router as repositories_router
from lintel.sandboxes_api.routes import router as sandboxes_router
from lintel.settings_api.channels_router import router as channels_settings_router
from lintel.settings_api.routes import router as settings_router
from lintel.skills_api.routes import router as skills_router
from lintel.teams.routes import router as teams_router
from lintel.telegram.webhook import router as telegram_router
from lintel.triggers_api.routes import router as triggers_router
from lintel.users.routes import router as users_router
from lintel.variables_api.routes import router as variables_router
from lintel.work_items_api.routes import router as work_items_router
from lintel.workflow_definitions_api.routes import router as workflow_definitions_router

if TYPE_CHECKING:
    from fastapi import FastAPI


def mount_routers(app: FastAPI) -> None:
    """Register all API routers on the application."""
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
    app.include_router(telegram_router, prefix="/api/v1", tags=["telegram"])
    app.include_router(channels_settings_router, prefix="/api/v1", tags=["channels"])
