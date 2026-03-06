"""FastAPI application with lifespan and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from lintel.api.middleware import CorrelationMiddleware
from lintel.api.routes import (
    admin,
    agents,
    approvals,
    credentials,
    events,
    health,
    metrics,
    pii,
    repositories,
    sandboxes,
    settings,
    skills,
    threads,
    workflow_definitions,
    workflows,
)
from lintel.api.routes.credentials import InMemoryCredentialStore
from lintel.api.routes.skills import InMemorySkillStore
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore

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

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.projection_engine = engine
    app.state.repository_store = repository_store
    app.state.skill_store = skill_store
    app.state.credential_store = credential_store

    yield
    # Cleanup


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Lintel", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health.router)
    app.include_router(threads.router, prefix="/api/v1")
    app.include_router(repositories.router, prefix="/api/v1")
    app.include_router(workflows.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(sandboxes.router, prefix="/api/v1")
    app.include_router(skills.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(pii.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(workflow_definitions.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")
    app.include_router(credentials.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    return app


app = create_app()
