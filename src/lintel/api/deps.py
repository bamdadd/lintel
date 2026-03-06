"""Dependency injection for FastAPI routes."""

from fastapi import Request

from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore


def get_thread_status_projection(request: Request) -> ThreadStatusProjection:
    """Get thread status projection from app state."""
    return request.app.state.thread_status_projection  # type: ignore[no-any-return]


def get_task_backlog_projection(request: Request) -> TaskBacklogProjection:
    """Get task backlog projection from app state."""
    return request.app.state.task_backlog_projection  # type: ignore[no-any-return]


def get_projection_engine(request: Request) -> InMemoryProjectionEngine:
    """Get projection engine from app state."""
    return request.app.state.projection_engine  # type: ignore[no-any-return]


def get_repository_store(request: Request) -> InMemoryRepositoryStore:
    """Get repository store from app state."""
    return request.app.state.repository_store  # type: ignore[no-any-return]
