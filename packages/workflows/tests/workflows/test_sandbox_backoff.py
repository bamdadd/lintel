"""Tests for sandbox pool backoff retry logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from lintel.sandbox.errors import NoSandboxAvailableError
from lintel.workflows.nodes._sandbox_backoff import acquire_pool_sandbox


class FakeSandboxStore:
    """In-memory sandbox store that can change between calls."""

    def __init__(self, snapshots: list[list[dict[str, Any]]]) -> None:
        self._snapshots = list(snapshots)
        self._call = 0

    async def list_all(self) -> list[dict[str, Any]]:
        idx = min(self._call, len(self._snapshots) - 1)
        self._call += 1
        return list(self._snapshots[idx])

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        idx = min(self._call - 1, len(self._snapshots) - 1)
        for entry in self._snapshots[idx]:
            if entry.get("sandbox_id") == sandbox_id:
                return entry
        return None


async def test_acquire_succeeds_first_attempt() -> None:
    """Returns sandbox_id immediately when a free sandbox is available."""
    store = FakeSandboxStore([[{"sandbox_id": "sbx-1"}]])
    manager = AsyncMock()
    manager.get_status = AsyncMock(return_value="running")

    result = await acquire_pool_sandbox(store, manager, delays=())
    assert result == "sbx-1"
    manager.get_status.assert_awaited_once_with("sbx-1")


async def test_acquire_skips_allocated_sandboxes() -> None:
    """Ignores sandboxes already allocated to a pipeline."""
    store = FakeSandboxStore([
        [{"sandbox_id": "sbx-busy", "pipeline_id": "run-1"}, {"sandbox_id": "sbx-free"}],
    ])
    manager = AsyncMock()
    manager.get_status = AsyncMock(return_value="running")

    result = await acquire_pool_sandbox(store, manager, delays=())
    assert result == "sbx-free"


async def test_acquire_retries_on_empty_pool() -> None:
    """Retries with backoff when pool is initially exhausted, succeeds on retry."""
    store = FakeSandboxStore([
        [{"sandbox_id": "sbx-1", "pipeline_id": "run-1"}],  # attempt 1: all busy
        [{"sandbox_id": "sbx-1"}],  # attempt 2: now free
    ])
    manager = AsyncMock()
    manager.get_status = AsyncMock(return_value="running")

    result = await acquire_pool_sandbox(store, manager, delays=(0.01,))
    assert result == "sbx-1"


async def test_acquire_retries_on_stale_sandbox() -> None:
    """Retries when the only free sandbox is stale (get_status raises)."""
    store = FakeSandboxStore([
        [{"sandbox_id": "sbx-stale"}],  # attempt 1: stale
        [{"sandbox_id": "sbx-good"}],   # attempt 2: healthy
    ])
    manager = AsyncMock()
    manager.get_status = AsyncMock(side_effect=[RuntimeError("container gone"), "running"])

    result = await acquire_pool_sandbox(store, manager, delays=(0.01,))
    assert result == "sbx-good"


async def test_acquire_raises_after_all_retries_exhausted() -> None:
    """Raises NoSandboxAvailableError after all attempts fail."""
    store = FakeSandboxStore([
        [{"sandbox_id": "sbx-1", "pipeline_id": "run-1"}],
        [{"sandbox_id": "sbx-1", "pipeline_id": "run-1"}],
        [{"sandbox_id": "sbx-1", "pipeline_id": "run-1"}],
        [{"sandbox_id": "sbx-1", "pipeline_id": "run-1"}],
    ])
    manager = AsyncMock()

    with pytest.raises(NoSandboxAvailableError):
        await acquire_pool_sandbox(store, manager, delays=(0.01, 0.01, 0.01))


async def test_acquire_calls_log_fn_on_retry() -> None:
    """Calls log_fn with a message on each retry."""
    store = FakeSandboxStore([
        [],  # attempt 1: empty
        [{"sandbox_id": "sbx-1"}],  # attempt 2: available
    ])
    manager = AsyncMock()
    manager.get_status = AsyncMock(return_value="running")

    log_messages: list[str] = []

    async def log_fn(msg: str) -> None:
        log_messages.append(msg)

    result = await acquire_pool_sandbox(store, manager, delays=(0.01,), log_fn=log_fn)
    assert result == "sbx-1"
    assert len(log_messages) == 1
    assert "attempt 1/2" in log_messages[0]
    assert "retrying" in log_messages[0].lower()


async def test_acquire_no_log_fn_on_success() -> None:
    """Does not call log_fn when acquisition succeeds on first attempt."""
    store = FakeSandboxStore([[{"sandbox_id": "sbx-1"}]])
    manager = AsyncMock()
    manager.get_status = AsyncMock(return_value="running")

    log_messages: list[str] = []

    async def log_fn(msg: str) -> None:
        log_messages.append(msg)

    await acquire_pool_sandbox(store, manager, delays=(0.01,), log_fn=log_fn)
    assert len(log_messages) == 0


async def test_acquire_default_delays() -> None:
    """Default delays are (5, 15, 30) giving 4 total attempts."""
    from lintel.workflows.nodes._sandbox_backoff import DEFAULT_DELAYS

    assert DEFAULT_DELAYS == (5.0, 15.0, 30.0)
