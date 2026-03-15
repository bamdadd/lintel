"""Asyncio semaphore-based concurrency limiter with NATS event emission.

Caps simultaneous agent slot acquisitions across all pipeline runs.
The slot count is controlled by LINTEL_MAX_CONCURRENT_AGENTS (default 5).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from lintel.contracts.concurrency import ConcurrencyState, SlotAcquiredEvent, SlotReleasedEvent

if TYPE_CHECKING:
    from uuid import UUID


class _EventBusProtocol(Protocol):
    """Minimal protocol for the event bus used by ConcurrencyLimiter."""

    async def publish(self, event: object) -> None: ...


class ConcurrencyLimiter:
    """Asyncio semaphore-backed concurrency limiter.

    Limits the number of simultaneous agent slot acquisitions and emits
    SlotAcquiredEvent / SlotReleasedEvent to the event bus on each transition.

    Args:
        max_slots: Maximum number of concurrent agent slots.
        event_bus: Event bus client for publishing lifecycle events.
    """

    def __init__(self, max_slots: int, event_bus: _EventBusProtocol) -> None:
        self._max_slots = max_slots
        self._semaphore = asyncio.Semaphore(max_slots)
        self._active = 0
        self._lock = asyncio.Lock()
        self._event_bus = event_bus

    async def acquire(self, agent_id: str, run_id: UUID) -> None:
        """Acquire a concurrency slot, blocking until one is available.

        Publishes a SlotAcquiredEvent after the slot is granted.
        """
        await self._semaphore.acquire()
        async with self._lock:
            self._active += 1
        event = SlotAcquiredEvent(
            agent_id=agent_id,
            run_id=run_id,
            acquired_at=datetime.now(tz=UTC),
        )
        await self._event_bus.publish(event)

    async def release(self, agent_id: str, run_id: UUID, outcome: str) -> None:
        """Release a concurrency slot.

        Publishes a SlotReleasedEvent after the slot is returned.
        """
        async with self._lock:
            self._active -= 1
        self._semaphore.release()
        event = SlotReleasedEvent(
            agent_id=agent_id,
            run_id=run_id,
            released_at=datetime.now(tz=UTC),
            outcome=outcome,
        )
        await self._event_bus.publish(event)

    @property
    def current_state(self) -> ConcurrencyState:
        """Return a snapshot of the current limiter state."""
        return ConcurrencyState(
            active_slots=self._active,
            max_slots=self._max_slots,
            queue_depth=len(self._semaphore._waiters or ()),
        )
