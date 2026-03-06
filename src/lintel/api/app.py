"""FastAPI application with lifespan and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from lintel.api.middleware import CorrelationMiddleware
from lintel.api.routes import health, threads
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection

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

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.projection_engine = engine

    yield
    # Cleanup


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Lintel", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health.router)
    app.include_router(threads.router, prefix="/api/v1")
    return app


app = create_app()
