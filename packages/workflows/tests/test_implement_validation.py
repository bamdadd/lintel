"""Tests for work item validation in the implement node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.workflows.nodes.implement import _validate_work_item, spawn_implementation

# ---------------------------------------------------------------------------
# _validate_work_item unit tests
# ---------------------------------------------------------------------------


class TestValidateWorkItem:
    def test_missing_work_item_returns_error(self) -> None:
        error = _validate_work_item({})
        assert error is not None
        assert "No work item" in error

    def test_none_work_item_returns_error(self) -> None:
        error = _validate_work_item({"work_item": None})
        assert error is not None
        assert "No work item" in error

    def test_empty_title_returns_error(self) -> None:
        error = _validate_work_item({"work_item": {"title": "", "description": "x" * 25}})
        assert error is not None
        assert "no title" in error

    def test_whitespace_only_title_returns_error(self) -> None:
        error = _validate_work_item({"work_item": {"title": "   ", "description": "x" * 25}})
        assert error is not None
        assert "no title" in error

    @pytest.mark.parametrize(
        "title",
        [
            "lintel: implement feature",
            "Lintel: Implement Feature",
            "LINTEL: IMPLEMENT FEATURE",
            "audit and harden",
            "Audit and Harden",
            "lintel: audit",
            "implement feature",
            "new feature",
            "feature request",
            "todo",
            "fix bug",
            "untitled",
        ],
    )
    def test_generic_title_returns_error(self, title: str) -> None:
        error = _validate_work_item({"work_item": {"title": title, "description": "x" * 25}})
        assert error is not None
        assert "generic" in error.lower()

    def test_short_description_returns_error(self) -> None:
        error = _validate_work_item(
            {"work_item": {"title": "Add rate limiting to API", "description": "short"}}
        )
        assert error is not None
        assert "description" in error.lower()

    def test_description_exactly_at_minimum_is_ok(self) -> None:
        desc = "x" * 20
        error = _validate_work_item(
            {"work_item": {"title": "Add rate limiting to API", "description": desc}}
        )
        assert error is None

    def test_valid_work_item_dict_returns_none(self) -> None:
        error = _validate_work_item(
            {
                "work_item": {
                    "title": "Add pagination to /api/v1/work-items endpoint",
                    "description": "Implement cursor-based pagination so that large result sets "
                    "are returned incrementally rather than all at once.",
                }
            }
        )
        assert error is None

    def test_valid_work_item_dataclass_style_returns_none(self) -> None:
        """Validation must also work with object-style work items (not just dicts)."""

        class FakeWorkItem:
            title = "Implement retry logic for sandbox execute"
            description = (
                "When sandbox.execute returns a transient error, "
                "retry up to 3 times with exponential back-off."
            )

        error = _validate_work_item({"work_item": FakeWorkItem()})
        assert error is None

    def test_generic_title_dataclass_style_returns_error(self) -> None:
        class FakeWorkItem:
            title = "lintel: implement feature"
            description = "Some long enough description here for testing."

        error = _validate_work_item({"work_item": FakeWorkItem()})
        assert error is not None
        assert "generic" in error.lower()

    def test_missing_description_key_returns_error(self) -> None:
        error = _validate_work_item({"work_item": {"title": "Add feature X"}})
        assert error is not None
        assert "description" in error.lower()

    def test_none_description_returns_error(self) -> None:
        error = _validate_work_item({"work_item": {"title": "Add feature X", "description": None}})
        assert error is not None
        assert "description" in error.lower()


# ---------------------------------------------------------------------------
# spawn_implementation integration tests (mocked infrastructure)
# ---------------------------------------------------------------------------


def _make_state(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "run_id": "run-test-123",
        "thread_ref": "ws:ch:ts",
        "sandbox_id": "sbx-1",
        "plan": {},
        "sanitized_messages": [],
        "workspace_path": "/workspace/repo",
        "workspace_paths": (),
        "review_cycles": 0,
        "agent_outputs": [],
    }
    base.update(overrides)
    return base


def _make_config(
    sandbox_manager: object = None,
    agent_runtime: object = None,
) -> dict[str, object]:
    return {
        "configurable": {
            "sandbox_manager": sandbox_manager,
            "agent_runtime": agent_runtime,
        }
    }


def _make_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.mark_running = AsyncMock()
    tracker.append_log = AsyncMock()
    tracker.mark_completed = AsyncMock()
    return tracker


class TestSpawnImplementationValidation:
    async def test_returns_error_when_no_work_item(self) -> None:
        state = _make_state()  # no work_item key
        config = _make_config()

        # StageTracker is a lazy import inside spawn_implementation — patch it at source
        with patch(
            "lintel.workflows.nodes._stage_tracking.StageTracker",
            return_value=_make_tracker(),
        ):
            result = await spawn_implementation(state, config)  # type: ignore[arg-type]

        assert result["current_phase"] == "closed"
        assert "No work item" in str(result["error"])

    async def test_returns_error_when_title_is_generic(self) -> None:
        state = _make_state(
            work_item={
                "title": "lintel: implement feature",
                "description": "Some description that is long enough to pass.",
            }
        )
        config = _make_config()

        with patch(
            "lintel.workflows.nodes._stage_tracking.StageTracker",
            return_value=_make_tracker(),
        ):
            result = await spawn_implementation(state, config)  # type: ignore[arg-type]

        assert result["current_phase"] == "closed"
        assert "generic" in str(result["error"]).lower()

    async def test_returns_error_when_description_too_short(self) -> None:
        state = _make_state(
            work_item={
                "title": "Add rate limiting to API endpoints",
                "description": "Too short.",
            }
        )
        config = _make_config()

        with patch(
            "lintel.workflows.nodes._stage_tracking.StageTracker",
            return_value=_make_tracker(),
        ):
            result = await spawn_implementation(state, config)  # type: ignore[arg-type]

        assert result["current_phase"] == "closed"
        assert "description" in str(result["error"]).lower()

    async def test_proceeds_past_validation_with_valid_work_item(self) -> None:
        """When the work item is valid, the node should NOT return early from validation."""
        state = _make_state(
            work_item={
                "title": "Add cursor-based pagination to work items API",
                "description": (
                    "Implement cursor-based pagination so that large result sets "
                    "are returned incrementally rather than all at once."
                ),
            },
            sandbox_id="",  # triggers a different early return (no sandbox)
        )
        config = _make_config()

        with patch(
            "lintel.workflows.nodes._stage_tracking.StageTracker",
            return_value=_make_tracker(),
        ):
            result = await spawn_implementation(state, config)  # type: ignore[arg-type]

        # Should NOT be a validation error — it must fail at the sandbox check instead
        error_str = str(result.get("error", "")).lower()
        assert "no work item" not in error_str
        assert "generic" not in error_str
        # The description check message won't appear either
        assert "minimum" not in error_str
        # It should fail with the sandbox-missing error
        assert "sandbox" in error_str
