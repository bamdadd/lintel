"""Tests for the test execution workflow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from lintel.contracts.types import SandboxResult
from lintel.workflows.nodes.test_code import _ensure_python_deps, run_tests

_STAGE = "lintel.workflows.nodes._stage_tracking"


def _make_state(**overrides: object) -> dict[str, object]:
    defaults: dict[str, Any] = {
        "run_id": "run-1",
        "sandbox_id": "sb-1",
        "workspace_path": "/workspace/repo",
        "thread_ref": "thread:W1:C1:ts1",
    }
    defaults.update(overrides)
    return defaults


def _make_config(sandbox_manager: object = None) -> dict[str, Any]:
    return {"configurable": {"sandbox_manager": sandbox_manager}}


def _mock_sandbox(
    *results: tuple[int, str, str],
) -> AsyncMock:
    """Create a mock sandbox manager that returns successive results."""
    mgr = AsyncMock()
    side_effects = [SandboxResult(exit_code=ec, stdout=out, stderr=err) for ec, out, err in results]
    mgr.execute = AsyncMock(side_effect=side_effects)
    mgr.reconnect_network = AsyncMock()
    mgr.disconnect_network = AsyncMock()
    return mgr


class TestRunTests:
    async def test_skips_when_no_sandbox(self) -> None:
        state = _make_state(sandbox_id=None)
        mgr = AsyncMock()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "skipped"

    async def test_detects_pyproject_and_runs_pytest(self) -> None:
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/pyproject.toml", ""),
            # _ensure_python_deps: which uv
            (0, "/root/.local/bin/uv", ""),
            # _ensure_python_deps: uv sync
            (0, "Resolved 10 packages", ""),
            # run pytest
            (0, "3 passed", ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"
        assert result["current_phase"] == "reviewing"

    async def test_failed_tests_report_failure(self) -> None:
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/package.json", ""),
            # npm test
            (1, "", "FAIL src/app.test.js"),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "failed"
        assert result["agent_outputs"][0]["exit_code"] == 1

    async def test_reconnects_network_for_python_deps(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/pyproject.toml", ""),
            (0, "/root/.local/bin/uv", ""),
            (0, "installed", ""),
            (0, "1 passed", ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
        ):
            await run_tests(state, config)

        mgr.reconnect_network.assert_called_once_with("sb-1")
        mgr.disconnect_network.assert_called_once_with("sb-1")

    async def test_no_test_runner_detected(self) -> None:
        mgr = _mock_sandbox(
            # detect files — nothing recognizable
            (0, "", ""),
            # echo 'No test runner detected'
            (0, "No test runner detected", ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"

    async def test_truncates_long_output(self) -> None:
        long_output = "x" * 6000
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Cargo.toml", ""),
            (1, long_output, ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
        ):
            result = await run_tests(state, config)

        output = result["agent_outputs"][0]["output"]
        assert "(truncated)" in output
        assert len(output) < 6000


class TestEnsurePythonDeps:
    async def test_skips_install_when_uv_present(self) -> None:
        mgr = _mock_sandbox(
            (0, "/root/.local/bin/uv", ""),
            (0, "Resolved 5 packages", ""),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        assert mgr.execute.call_count == 2

    async def test_installs_uv_when_missing(self) -> None:
        mgr = _mock_sandbox(
            (0, "MISSING", ""),
            (0, "uv installed", ""),
            (0, "", ""),
            (0, "Resolved 5 packages", ""),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        assert mgr.execute.call_count == 4

    async def test_handles_uv_install_failure(self) -> None:
        mgr = _mock_sandbox(
            (0, "MISSING", ""),
            (1, "", "curl failed"),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        # Should stop after failed install (no uv sync)
        assert mgr.execute.call_count == 2

    async def test_handles_sync_failure(self) -> None:
        mgr = _mock_sandbox(
            (0, "/root/.local/bin/uv", ""),
            (1, "", "resolution failed"),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        # Should still complete without raising
        assert mgr.execute.call_count == 2
