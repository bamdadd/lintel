"""Subscription patterns for the event bus.

Provides catch-up, live, and filtered subscription helpers
that compose EventStore reads with EventBus subscriptions.

Gap-free catch-up strategy
--------------------------
A naïve catch-up (replay historical, *then* subscribe to live) has a window
where events published between the end of replay and the start of the live
subscription are silently lost.

The correct approach — inspired by EventStoreDB persistent subscriptions — is:

1. Subscribe to the live bus **first**, buffering incoming events.
2. Replay historical events from the store and deliver them to the handler.
3. Drain the buffer, skipping any events already seen during replay.

This guarantees at-least-once delivery with no gaps.  Duplicates are
filtered by ``event_id``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus, EventHandler, EventStore

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Subscription handle
# ---------------------------------------------------------------------------


@dataclass
class Subscription:
    """Handle returned by subscription helpers for lifecycle management.

    Callers use ``await subscription.unsubscribe()`` to detach from the bus.
    """

    subscription_id: str
    event_bus: EventBus
    event_types: frozenset[str]
    _active: bool = field(default=True, repr=False)

    async def unsubscribe(self) -> None:
        """Detach from the event bus. Idempotent."""
        if self._active:
            await self.event_bus.unsubscribe(self.subscription_id)
            self._active = False

    @property
    def active(self) -> bool:
        return self._active


# ---------------------------------------------------------------------------
# Internal buffering handler used by catch-up subscribe
# ---------------------------------------------------------------------------


class _BufferingHandler:
    """Collects live events into a queue while historical replay is running.

    After replay finishes the owner drains the buffer, de-duplicates against
    already-seen event IDs, and forwards unseen events to the real handler.
    Once the buffer is drained the handler switches to *pass-through* mode
    where every subsequent event goes directly to the real handler.
    """

    def __init__(self, handler: EventHandler) -> None:
        self._handler = handler
        self._buffer: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        self._pass_through = False

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — called by the EventBus."""
        if self._pass_through:
            await self._handler.handle(event)
        else:
            await self._buffer.put(event)

    async def drain(self, seen_ids: set[UUID]) -> None:
        """Drain buffered events, skipping those already replayed.

        After draining, switches to pass-through mode so future events
        bypass the buffer entirely.
        """
        drained = 0
        duplicates = 0
        while not self._buffer.empty():
            event = self._buffer.get_nowait()
            if event.event_id in seen_ids:
                duplicates += 1
                continue
            await self._handler.handle(event)
            seen_ids.add(event.event_id)
            drained += 1
        self._pass_through = True
        logger.debug(
            "catch_up_buffer_drained",
            drained=drained,
            duplicates_skipped=duplicates,
        )


# ---------------------------------------------------------------------------
# Public subscription helpers
# ---------------------------------------------------------------------------


async def catch_up_subscribe(
    event_store: EventStore,
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
    from_position: int = 0,
) -> Subscription:
    """Read all historical events, then switch to live bus delivery.

    Uses the gap-free strategy described in the module docstring:

    1. Subscribe to the live bus with a buffering handler.
    2. Replay historical events from the store to the real handler,
       collecting seen ``event_id``\\s.
    3. Drain the buffer, skipping duplicates.
    4. Switch the buffering handler to pass-through mode.

    Returns a :class:`Subscription` for lifecycle management.
    """
    # Step 1 — subscribe to live bus *first* so no events are lost
    buffering = _BufferingHandler(handler)
    subscription_id = await event_bus.subscribe(event_types, buffering)

    # Step 2 — replay historical events
    seen_ids: set[UUID] = set()
    replay_count = 0
    for event_type in sorted(event_types):
        historical = await event_store.read_by_event_type(event_type, from_position)
        for event in historical:
            await handler.handle(event)
            seen_ids.add(event.event_id)
            replay_count += 1

    logger.info(
        "catch_up_replay_complete",
        event_types=sorted(event_types),
        from_position=from_position,
        replayed=replay_count,
    )

    # Step 3 — drain anything that arrived while replaying
    await buffering.drain(seen_ids)

    return Subscription(
        subscription_id=subscription_id,
        event_bus=event_bus,
        event_types=event_types,
    )


async def live_subscribe(
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
) -> Subscription:
    """Subscribe to live events only (no historical replay).

    Used for real-time notifications, guardrail evaluation, and
    Slack message updates that only care about events from *now*.

    Returns a :class:`Subscription` for lifecycle management.
    """
    subscription_id = await event_bus.subscribe(event_types, handler)
    logger.info(
        "live_subscribe",
        event_types=sorted(event_types) if event_types else ["*"],
        subscription_id=subscription_id,
    )
    return Subscription(
        subscription_id=subscription_id,
        event_bus=event_bus,
        event_types=event_types,
    )


async def filtered_subscribe(
    event_bus: EventBus,
    event_types: frozenset[str],
    handler: EventHandler,
) -> Subscription:
    """Subscribe to a specific subset of event types.

    Semantically distinct from :func:`live_subscribe` — used when the
    subscriber only cares about specific event types (e.g., a deployment
    metrics projection only needs ``DeploymentStarted/Succeeded/Failed``).

    Raises :class:`ValueError` if *event_types* is empty.

    Returns a :class:`Subscription` for lifecycle management.
    """
    if not event_types:
        msg = "filtered_subscribe requires at least one event type"
        raise ValueError(msg)

    subscription_id = await event_bus.subscribe(event_types, handler)
    logger.info(
        "filtered_subscribe",
        event_types=sorted(event_types),
        subscription_id=subscription_id,
    )
    return Subscription(
        subscription_id=subscription_id,
        event_bus=event_bus,
        event_types=event_types,
    )
