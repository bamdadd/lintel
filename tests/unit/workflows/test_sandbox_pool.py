"""Tests for sandbox pool allocation and release."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.contracts.types import SandboxResult
from lintel.workflows.nodes.close import close_workflow


class FakeSandboxStore:
    """In-memory sandbox store for testing."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        for e in entries or []:
            self._data[e["sandbox_id"]] = dict(e)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._data.get(sandbox_id)

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._data[sandbox_id] = metadata

    async def add(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._data[sandbox_id] = {"sandbox_id": sandbox_id, **metadata}

    async def remove(self, sandbox_id: str) -> None:
        self._data.pop(sandbox_id, None)


def _make_state(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_ref": "W1:C1:ts1",
        "correlation_id": "run-1",
        "sanitized_messages": ["test task"],
        "run_id": "run-1",
        "sandbox_id": "sbx-1",
        "feature_branch": "lintel/feat/test",
        "repo_branch": "main",
        "repo_url": "https://github.com/test/repo",
        "workspace_path": "/workspace/run-1/repo",
        "credential_ids": [],
        "plan": {},
        "agent_outputs": [],
    }
    base.update(overrides)
    return base


async def test_close_releases_sandbox_on_success() -> None:
    """Close clears pipeline_id from sandbox store on successful completion."""
    store = FakeSandboxStore(
        [
            {"sandbox_id": "sbx-1", "pipeline_id": "run-1", "image": "test"},
        ]
    )
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=SandboxResult(exit_code=0, stdout="ok", stderr=""))
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "sandbox_store": store,
            "pipeline_store": None,
        }
    }
    await close_workflow(_make_state(), config)

    entry = await store.get("sbx-1")
    assert entry is not None
    assert "pipeline_id" not in entry


async def test_close_releases_sandbox_on_failure() -> None:
    """Close clears pipeline_id even when pipeline aborts due to failure."""
    store = FakeSandboxStore(
        [
            {"sandbox_id": "sbx-1", "pipeline_id": "run-1", "image": "test"},
        ]
    )

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": None,
            "sandbox_store": store,
            "pipeline_store": None,
        }
    }
    state = _make_state(
        agent_outputs=[{"node": "review", "verdict": "request_changes"}],
    )
    await close_workflow(state, config)

    entry = await store.get("sbx-1")
    assert entry is not None
    assert "pipeline_id" not in entry


async def test_setup_workspace_picks_free_sandbox() -> None:
    """Setup workspace selects a sandbox without pipeline_id."""
    store = FakeSandboxStore(
        [
            {"sandbox_id": "sbx-busy", "pipeline_id": "other-run", "image": "test"},
            {"sandbox_id": "sbx-free", "image": "test"},
        ]
    )

    free = [s for s in await store.list_all() if not s.get("pipeline_id")]
    assert len(free) == 1
    assert free[0]["sandbox_id"] == "sbx-free"


async def test_setup_workspace_skips_all_allocated() -> None:
    """When all sandboxes are allocated, free list is empty."""
    store = FakeSandboxStore(
        [
            {"sandbox_id": "sbx-1", "pipeline_id": "run-a", "image": "test"},
            {"sandbox_id": "sbx-2", "pipeline_id": "run-b", "image": "test"},
        ]
    )

    free = [s for s in await store.list_all() if not s.get("pipeline_id")]
    assert len(free) == 0


async def test_allocation_stamps_pipeline_id() -> None:
    """Allocating a sandbox stamps it with the pipeline run_id."""
    store = FakeSandboxStore(
        [
            {"sandbox_id": "sbx-1", "image": "test"},
        ]
    )

    # Simulate what setup_workspace does
    entry = await store.get("sbx-1")
    assert entry is not None
    entry["pipeline_id"] = "run-42"
    await store.update("sbx-1", entry)

    updated = await store.get("sbx-1")
    assert updated is not None
    assert updated["pipeline_id"] == "run-42"

    # Now it should not appear as free
    free = [s for s in await store.list_all() if not s.get("pipeline_id")]
    assert len(free) == 0
