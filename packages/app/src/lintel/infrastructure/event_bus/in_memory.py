"""In-memory event bus with async pub/sub for domain events.

Future improvements (nice-to-have):
- Queue-per-subscriber: Replace asyncio.create_task-per-delivery with a dedicated
  asyncio.Queue per subscriber and a consumer loop. This gives backpressure control
  and preserves event ordering within a subscriber (current design can deliver out
  of order under contention, which is a correctness risk for projections).
- Remove set_event_bus() setter: Create the bus before store factories so it can be
  passed via constructor, eliminating the mutable post-construction wiring.
- Late projection registration: If a projection is registered after engine.start(),
  it won't receive events. Either re-subscribe with updated event types or block
  late registration with a clear error.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventHandler

logger = structlog.get_logger()


@dataclass
class _Subscription:
    """Internal subscription record."""

    subscription_id: str
    event_types: frozenset[str]
    handler: EventHandler
    queue: asyncio.Queue[EventEnvelope] = field(default_factory=asyncio.Queue)


class InMemoryEventBus:
    """Implements EventBus protocol with in-memory async queues.

    Each subscriber gets its own asyncio.Queue. Events are filtered
    by type at publish time and dispatched to matching subscribers.
    Failed handler invocations are logged but never block the publisher.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, _Subscription] = {}
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []

    async def publish(self, event: EventEnvelope) -> None:
        """Publish an event to all matching subscribers.

        Fire-and-forget: errors in individual handlers are logged,
        never propagated to the publisher.
        """
        async with self._lock:
            subs = list(self._subscriptions.values())

        for sub in subs:
            if not sub.event_types or event.event_type in sub.event_types:
                task = asyncio.create_task(
                    self._deliver(sub, event),
                    name=f"event-bus-deliver-{sub.subscription_id}-{event.event_type}",
                )
                self._tasks.append(task)
                task.add_done_callback(self._tasks.remove)

    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: EventHandler,
    ) -> str:
        """Register a handler for the given event types.

        Returns a subscription ID for later unsubscription.
        Pass an empty frozenset to receive all events.
        """
        subscription_id = str(uuid4())
        sub = _Subscription(
            subscription_id=subscription_id,
            event_types=event_types,
            handler=handler,
        )
        async with self._lock:
            self._subscriptions[subscription_id] = sub
        logger.info(
            "event_bus_subscribed",
            subscription_id=subscription_id,
            event_types=sorted(event_types) if event_types else ["*"],
        )
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by ID."""
        async with self._lock:
            removed = self._subscriptions.pop(subscription_id, None)
        if removed:
            logger.info("event_bus_unsubscribed", subscription_id=subscription_id)

    @staticmethod
    async def _deliver(sub: _Subscription, event: EventEnvelope) -> None:
        """Deliver a single event to a subscriber, catching errors."""
        try:
            await sub.handler.handle(event)
        except Exception:
            logger.warning(
                "event_bus_handler_error",
                subscription_id=sub.subscription_id,
                event_type=event.event_type,
                exc_info=True,
            )

    @property
    def subscription_count(self) -> int:
        """Number of active subscriptions (for diagnostics)."""
        return len(self._subscriptions)
