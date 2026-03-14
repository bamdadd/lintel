"""Background automation scheduler with cron evaluation and concurrency control."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from croniter import croniter  # type: ignore[import-untyped]

from lintel.contracts.types import AutomationTriggerType, ConcurrencyPolicy

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from uuid import UUID


class AutomationScheduler:
    """Evaluates cron schedules and enforces concurrency policies."""

    TICK_INTERVAL_SECONDS = 60

    def __init__(
        self,
        automation_store: Any,  # noqa: ANN401
        fire_fn: Callable[..., Coroutine[Any, Any, str]],
        skip_fn: Callable[..., Coroutine[Any, Any, None]] | None = None,
        cancel_fn: Callable[..., Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._store = automation_store
        self._fire_fn = fire_fn
        self._skip_fn = skip_fn or _noop_skip
        self._cancel_fn = cancel_fn or _noop_cancel
        self._last_fired: dict[str, datetime] = {}
        self._active_runs: dict[str, str] = {}  # automation_id -> run_id
        self._queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._chain_depths: dict[UUID, int] = {}  # correlation_id -> depth

    async def tick_cron(self) -> list[str]:
        """Evaluate all cron automations. Returns list of fired automation IDs."""
        all_automations = await self._store.list_all()
        now = datetime.now(UTC)
        fired: list[str] = []

        for auto in all_automations:
            if not auto.enabled:
                continue
            if auto.trigger_type != AutomationTriggerType.CRON:
                continue

            schedule = auto.trigger_config.get("schedule")
            if not schedule:
                continue

            if not self._is_due(auto.automation_id, str(schedule), now):
                continue

            result = await self._apply_concurrency(auto, {"trigger": "cron"})
            if result:
                fired.append(auto.automation_id)

        return fired

    def _is_due(self, automation_id: str, schedule: str, now: datetime) -> bool:
        """Check if a cron automation is due to fire."""
        last = self._last_fired.get(automation_id)
        cron = croniter(schedule, now)
        prev = cron.get_prev(datetime).replace(tzinfo=UTC)

        return not (last is not None and last >= prev)

    async def _apply_concurrency(
        self,
        auto: Any,  # noqa: ANN401
        trigger_metadata: dict[str, Any],
    ) -> bool:
        """Apply concurrency policy. Returns True if fired."""
        aid: str = auto.automation_id
        active = self._active_runs.get(aid)

        if auto.concurrency_policy == ConcurrencyPolicy.ALLOW:
            await self._fire_fn(auto, trigger_metadata)
            self._last_fired[aid] = datetime.now(UTC)
            return True

        if active is None:
            run_id = await self._fire_fn(auto, trigger_metadata)
            self._active_runs[aid] = run_id
            self._last_fired[aid] = datetime.now(UTC)
            return True

        if auto.concurrency_policy == ConcurrencyPolicy.SKIP:
            await self._skip_fn(auto, "concurrency:skip")
            return False

        if auto.concurrency_policy == ConcurrencyPolicy.QUEUE:
            self._queues[aid].append(trigger_metadata)
            return False

        if auto.concurrency_policy == ConcurrencyPolicy.CANCEL:
            await self._cancel_fn(aid, active)
            run_id = await self._fire_fn(auto, trigger_metadata)
            self._active_runs[aid] = run_id
            self._last_fired[aid] = datetime.now(UTC)
            return True

        return False

    async def handle_event(self, event: Any) -> None:  # noqa: ANN401
        """Handle an incoming domain event, firing matching automations."""
        all_automations = await self._store.list_all()
        for auto in all_automations:
            if not auto.enabled:
                continue
            if auto.trigger_type != AutomationTriggerType.EVENT:
                continue
            event_types = auto.trigger_config.get("event_types", [])
            if event.event_type not in event_types:
                continue

            # Chain depth guard
            corr_id: UUID | None = getattr(event, "correlation_id", None)
            if corr_id is not None:
                depth = self._chain_depths.get(corr_id, 0)
                if depth >= auto.max_chain_depth:
                    await self._skip_fn(auto, "max_chain_depth_exceeded")
                    continue

            metadata = {"trigger": "event", "event_type": event.event_type}
            result = await self._apply_concurrency(auto, metadata)
            if result and corr_id is not None:
                self._chain_depths[corr_id] = self._chain_depths.get(corr_id, 0) + 1

    async def mark_run_completed(self, automation_id: str, run_id: str) -> None:
        """Called when a pipeline run completes — dequeue next if queued."""
        if self._active_runs.get(automation_id) == run_id:
            del self._active_runs[automation_id]

        queue = self._queues.get(automation_id, [])
        if queue:
            metadata = queue.pop(0)
            auto = await self._store.get(automation_id)
            if auto and auto.enabled:
                new_run_id = await self._fire_fn(auto, metadata)
                self._active_runs[automation_id] = new_run_id

    async def run(self) -> None:
        """Run the cron scheduler loop indefinitely."""
        while True:
            await self.tick_cron()
            await asyncio.sleep(self.TICK_INTERVAL_SECONDS)


async def _noop_skip(auto: Any, reason: str) -> None:  # noqa: ANN401
    """No-op skip callback."""


async def _noop_cancel(automation_id: str, run_id: str) -> None:
    """No-op cancel callback."""
