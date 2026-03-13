"""Dependency injection for FastAPI routes."""

from fastapi import Request

from lintel.domain.command_dispatcher import InMemoryCommandDispatcher
from lintel.infrastructure.event_store.in_memory import InMemoryEventStore
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.quality_metrics import QualityMetricsProjection
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore


def get_quality_metrics_projection(request: Request) -> QualityMetricsProjection:
    """Get quality metrics projection from app state."""
    return request.app.state.quality_metrics_projection  # type: ignore[no-any-return]


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


def get_event_store(request: Request) -> InMemoryEventStore:
    """Get event store from app state."""
    return request.app.state.event_store  # type: ignore[no-any-return]


def get_command_dispatcher(request: Request) -> InMemoryCommandDispatcher:
    """Get command dispatcher from app state."""
    return request.app.state.command_dispatcher  # type: ignore[no-any-return]
