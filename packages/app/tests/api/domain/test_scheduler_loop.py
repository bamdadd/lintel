"""Tests for SchedulerLoop."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.api.domain.scheduler_loop import SchedulerLoop


async def test_tick_acquires_lock_and_runs_scheduler() -> None:
    coordinator = AsyncMock()
    coordinator.try_acquire_scheduler_lock.return_value = True
    scheduler = AsyncMock()
    scheduler.tick.return_value = ["run-1"]

    loop = SchedulerLoop(coordinator=coordinator, scheduler=scheduler)
    # Run a single tick
    runs = await loop.single_tick()

    assert runs == ["run-1"]
    coordinator.try_acquire_scheduler_lock.assert_called_once()
    coordinator.release_scheduler_lock.assert_called_once()
    scheduler.tick.assert_called_once()


async def test_tick_skips_when_lock_unavailable() -> None:
    coordinator = AsyncMock()
    coordinator.try_acquire_scheduler_lock.return_value = False
    scheduler = AsyncMock()

    loop = SchedulerLoop(coordinator=coordinator, scheduler=scheduler)
    runs = await loop.single_tick()

    assert runs == []
    scheduler.tick.assert_not_called()
    coordinator.release_scheduler_lock.assert_not_called()
