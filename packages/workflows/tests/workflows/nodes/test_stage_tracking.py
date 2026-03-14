"""Tests for StageTracker lifecycle hooks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lintel.workflows.nodes._stage_tracking import StageTracker


@pytest.fixture()
def mock_config() -> dict:
    pipeline_store = AsyncMock()
    pipeline_store.get.return_value = None
    return {
        "configurable": {
            "run_id": "run-1",
            "pipeline_store": pipeline_store,
            "app_state": MagicMock(pipeline_store=pipeline_store),
        },
    }


class TestStageLifecycleHooks:
    async def test_on_success_called_on_completion(self, mock_config: dict) -> None:
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_success=callback)
        await tracker.mark_completed("research", outputs={"research_report": "report"})
        callback.assert_awaited_once_with("research", {"research_report": "report"})

    async def test_on_failure_called_on_error(self, mock_config: dict) -> None:
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_failure=callback)
        await tracker.mark_completed("research", error="boom")
        callback.assert_awaited_once_with("research", "boom")

    async def test_on_success_not_called_on_error(self, mock_config: dict) -> None:
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_success=callback)
        await tracker.mark_completed("research", error="boom")
        callback.assert_not_awaited()

    async def test_on_failure_not_called_on_success(self, mock_config: dict) -> None:
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_failure=callback)
        await tracker.mark_completed("research", outputs={"x": 1})
        callback.assert_not_awaited()

    async def test_hooks_default_to_none(self, mock_config: dict) -> None:
        tracker = StageTracker(mock_config)
        # Should not raise
        await tracker.mark_completed("research", outputs={"x": 1})

    async def test_on_success_exception_does_not_propagate(self, mock_config: dict) -> None:
        callback = AsyncMock(side_effect=RuntimeError("hook failed"))
        tracker = StageTracker(mock_config, on_success=callback)
        # Should not raise
        await tracker.mark_completed("research", outputs={"x": 1})
        callback.assert_awaited_once()

    async def test_on_failure_exception_does_not_propagate(self, mock_config: dict) -> None:
        callback = AsyncMock(side_effect=RuntimeError("hook failed"))
        tracker = StageTracker(mock_config, on_failure=callback)
        # Should not raise
        await tracker.mark_completed("research", error="boom")
        callback.assert_awaited_once()
