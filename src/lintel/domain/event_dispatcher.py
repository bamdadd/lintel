"""Dispatch domain events to the event store and projection engine.

Routes and domain services use ``dispatch_event`` to publish facts.
The projection engine fans them out to registered projections (audit,
webhooks, notifications, etc.) so consumers never couple to producers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from fastapi import Request

    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()


async def dispatch_event(
    request: Request,
    event: EventEnvelope,
    *,
    stream_id: str = "admin",
) -> None:
    """Append *event* to the event store and project it.

    Parameters
    ----------
    request:
        The current FastAPI request (provides ``app.state``).
    event:
        The domain event to publish.
    stream_id:
        The logical stream the event belongs to (e.g. ``"project:{id}"``).
    """
    event_store = getattr(request.app.state, "event_store", None)
    if event_store is not None:
        try:
            await event_store.append(stream_id=stream_id, events=[event])
        except Exception:
            logger.warning(
                "event_store_append_failed",
                event_type=event.event_type,
                stream_id=stream_id,
            )

    engine = getattr(request.app.state, "projection_engine", None)
    if engine is not None:
        try:
            await engine.project(event)
        except Exception:
            logger.warning(
                "projection_failed",
                event_type=event.event_type,
            )


async def dispatch_event_raw(
    app_state: Any,  # noqa: ANN401
    event: EventEnvelope,
    *,
    stream_id: str = "admin",
) -> None:
    """Like ``dispatch_event`` but accepts ``app.state`` directly.

    Useful in domain services (e.g. ``WorkflowExecutor``) that don't
    have a ``Request`` object.
    """
    event_store = getattr(app_state, "event_store", None)
    if event_store is not None:
        try:
            await event_store.append(stream_id=stream_id, events=[event])
        except Exception:
            logger.warning(
                "event_store_append_failed",
                event_type=event.event_type,
                stream_id=stream_id,
            )

    engine = getattr(app_state, "projection_engine", None)
    if engine is not None:
        try:
            await engine.project(event)
        except Exception:
            logger.warning(
                "projection_failed",
                event_type=event.event_type,
            )
