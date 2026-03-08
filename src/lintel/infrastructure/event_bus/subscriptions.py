"""Subscription patterns for the event bus.

Provides catch-up, live, and filtered subscription helpers
that compose EventStore reads with EventBus subscriptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.protocols import EventBus, EventHandler, EventStore

logger = structlog.get_logger()


async def catch_up_subscribe(
    event_store: EventStore,
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
    from_position: int = 0,
) -> str:
    """Read all historical events, then switch to live bus delivery.

    1. Reads historical events matching event_types from the store
    2. Delivers each to the handler sequentially
    3. Subscribes to the bus for live events going forward

    Returns the subscription_id for later unsubscription.
    """
    # Phase 1: Replay historical events
    for event_type in sorted(event_types):
        historical = await event_store.read_by_event_type(event_type, from_position)
        for event in historical:
            await handler.handle(event)

    logger.info(
        "catch_up_replay_complete",
        event_types=sorted(event_types),
        from_position=from_position,
    )

    # Phase 2: Switch to live
    return await event_bus.subscribe(event_types, handler)


async def live_subscribe(
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
) -> str:
    """Subscribe to live events only (no historical replay).

    Returns the subscription_id for later unsubscription.
    """
    return await event_bus.subscribe(event_types, handler)


async def filtered_subscribe(
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
) -> str:
    """Subscribe to a specific subset of event types.

    Equivalent to live_subscribe but semantically distinct:
    used when the subscriber only cares about specific event types
    (e.g., deployment metrics projection only needs Deployment* events).

    Returns the subscription_id for later unsubscription.
    """
    if not event_types:
        msg = "filtered_subscribe requires at least one event type"
        raise ValueError(msg)
    return await event_bus.subscribe(event_types, handler)
