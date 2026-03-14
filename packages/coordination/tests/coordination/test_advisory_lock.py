"""Tests for AdvisoryLockCoordinator."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from lintel.coordination.advisory_lock import AdvisoryLockCoordinator

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def _make_pool(conn: AsyncMock) -> AsyncMock:
    pool = AsyncMock()

    @asynccontextmanager
    async def acquire() -> AsyncGenerator[AsyncMock]:
        yield conn

    pool.acquire = acquire
    return pool


async def test_try_acquire_returns_true_when_lock_available() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = True

    coordinator = AdvisoryLockCoordinator(pool=_make_pool(conn))
    result = await coordinator.try_acquire_scheduler_lock()

    assert result is True


async def test_try_acquire_returns_false_when_lock_held() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = False

    coordinator = AdvisoryLockCoordinator(pool=_make_pool(conn))
    result = await coordinator.try_acquire_scheduler_lock()

    assert result is False


async def test_release_calls_advisory_unlock() -> None:
    conn = AsyncMock()
    coordinator = AdvisoryLockCoordinator(pool=_make_pool(conn))
    await coordinator.release_scheduler_lock()

    conn.execute.assert_called_once()
