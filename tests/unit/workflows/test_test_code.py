"""Tests for the test execution workflow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from lintel.contracts.types import SandboxResult
from lintel.workflows.nodes.test_code import (
    _ensure_python_deps,
    _pick_test_target_from_output,
    run_tests,
)

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

    async def test_discovers_makefile_test_target(self) -> None:
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/Makefile\n/workspace/repo/pyproject.toml", ""),
            # make help
            (0, "test         Run all tests\nlint         Lint code\n", ""),
            # _ensure_python_deps: which uv
            (0, "/root/.local/bin/uv", ""),
            # _ensure_python_deps: uv sync
            (0, "Resolved 10 packages", ""),
            # _ensure_python_deps: spacy download
            (0, "en_core_web_sm installed", ""),
            # make test
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
        # Should have run `make test`
        last_exec = mgr.execute.call_args_list[-1]
        assert "make test" in last_exec[0][1].command

    async def test_falls_back_to_pytest_without_makefile(self) -> None:
        mgr = _mock_sandbox(
            # detect files — pyproject.toml only
            (0, "/workspace/repo/pyproject.toml", ""),
            # _ensure_python_deps: which uv
            (0, "/root/.local/bin/uv", ""),
            # _ensure_python_deps: uv sync
            (0, "Resolved 10 packages", ""),
            # _ensure_python_deps: spacy download
            (0, "en_core_web_sm installed", ""),
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
        last_exec = mgr.execute.call_args_list[-1]
        assert "pytest" in last_exec[0][1].command

    async def test_failed_tests_report_failure(self) -> None:
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/package.json", ""),
            # grep for test script
            (0, "HAS_TEST", ""),
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

    async def test_reconnects_network(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Cargo.toml", ""),
            (0, "test result: ok", ""),
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
        # disconnect_network called after test execution completes
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

    async def test_makefile_fallback_to_grep_targets(self) -> None:
        """When make help fails, falls back to parsing Makefile targets."""
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/Makefile", ""),
            # make help — no output
            (0, "", ""),
            # grep targets
            (0, "build\ntest\nclean\n", ""),
            # make test
            (0, "ok", ""),
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
        last_exec = mgr.execute.call_args_list[-1]
        assert "make test" in last_exec[0][1].command

    async def test_npm_test_with_package_json(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/package.json", ""),
            # grep for test script
            (0, "HAS_TEST", ""),
            (0, "Tests passed", ""),
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
        last_exec = mgr.execute.call_args_list[-1]
        assert "npm test" in last_exec[0][1].command


class TestPickTestTarget:
    def test_prefers_test_over_all(self) -> None:
        output = "lint\nall\ntest\nclean"
        assert _pick_test_target_from_output(output) == "test"

    def test_picks_test(self) -> None:
        output = "build\ntest\nclean"
        assert _pick_test_target_from_output(output) == "test"

    def test_picks_check(self) -> None:
        output = "build\ncheck\nclean"
        assert _pick_test_target_from_output(output) == "check"

    def test_returns_none_when_no_match(self) -> None:
        output = "build\nclean\ndeploy"
        assert _pick_test_target_from_output(output) is None

    def test_handles_make_help_format(self) -> None:
        output = "test         Run all tests\nlint         Lint code"
        assert _pick_test_target_from_output(output) == "test"

    def test_prefers_test_all(self) -> None:
        output = "test-unit\ntest-all\nverify"
        assert _pick_test_target_from_output(output) == "test-all"


class TestEnsurePythonDeps:
    async def test_skips_install_when_uv_present(self) -> None:
        mgr = _mock_sandbox(
            (0, "/root/.local/bin/uv", ""),
            (0, "Resolved 5 packages", ""),
            (0, "en_core_web_sm installed", ""),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        assert mgr.execute.call_count == 3

    async def test_installs_uv_when_missing(self) -> None:
        mgr = _mock_sandbox(
            (0, "MISSING", ""),
            (0, "uv installed", ""),
            (0, "", ""),
            (0, "Resolved 5 packages", ""),
            (0, "en_core_web_sm installed", ""),
        )
        config: dict[str, Any] = {"configurable": {}}
        state = _make_state()

        with patch(f"{_STAGE}.append_log", new_callable=AsyncMock):
            await _ensure_python_deps(mgr, "sb-1", "/workspace/repo", config, state)

        assert mgr.execute.call_count == 5

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
