"""Tests for the test execution workflow node."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes.test_code import run_tests

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
    # Ensure execute_stream is not callable so _stream_execute_with_logging falls back to execute()
    mgr.execute_stream = None
    return mgr


def _patch_discovery(
    test_command: str,
    setup_commands: list[str] | None = None,
) -> AbstractContextManager[AsyncMock]:
    """Patch the discover_test_command skill to return a fixed result."""
    result: dict[str, Any] = {"test_command": test_command}
    if setup_commands is not None:
        result["setup_commands"] = setup_commands
    else:
        result["setup_commands"] = []
    return patch(
        "lintel.api.domain.skills.discover_test_command.discover_test_command",
        new_callable=AsyncMock,
        return_value=result,
    )


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

    async def test_uses_discovered_test_command(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),  # git diff (no changed test files)
            (0, "3 passed", ""),  # test execution
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("make test"),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"
        assert result["current_phase"] == "reviewing"
        # The test command should be what the skill returned
        last_exec = mgr.execute.call_args_list[-1]
        assert "make test" in last_exec[0][1].command

    async def test_runs_setup_commands_before_test(self) -> None:
        mgr = _mock_sandbox(
            (0, "deps installed", ""),  # setup command
            (0, "", ""),  # git diff
            (0, "3 passed", ""),  # test execution
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("make test", setup_commands=["uv sync --all-extras"]),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"
        # First execute = setup, second = git diff, third = test
        assert mgr.execute.call_count == 3
        assert "uv sync" in mgr.execute.call_args_list[0][0][1].command

    async def test_runs_changed_tests_when_available(self) -> None:
        mgr = _mock_sandbox(
            (0, "tests/unit/api/test_health.py\n", ""),  # git diff
            (0, "1 passed", ""),  # test execution
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("make test-unit"),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"
        last_exec = mgr.execute.call_args_list[-1]
        assert "test_health.py" in last_exec[0][1].command
        assert "pytest" in last_exec[0][1].command

    async def test_failed_tests_report_failure(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),  # git diff
            (1, "", "FAIL src/app.test.js"),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("npm test"),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "failed"
        assert result["agent_outputs"][0]["exit_code"] == 1

    async def test_reconnects_and_disconnects_network(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),  # git diff
            (0, "ok", ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("cargo test"),
        ):
            await run_tests(state, config)

        mgr.reconnect_network.assert_called_once_with("sb-1")
        mgr.disconnect_network.assert_called_once_with("sb-1")

    async def test_truncates_long_output(self) -> None:
        long_output = "x" * 6000
        mgr = _mock_sandbox(
            (0, "", ""),  # git diff
            (1, long_output, ""),
        )
        state = _make_state()
        config = _make_config(mgr)

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("cargo test"),
        ):
            result = await run_tests(state, config)

        output = result["agent_outputs"][0]["output"]
        assert "(truncated)" in output
        assert len(output) < 6000

    async def test_persists_test_result(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),  # git diff
            (0, "5 passed", ""),
        )
        state = _make_state()
        result_store = AsyncMock()
        added: list[Any] = []
        result_store.add = AsyncMock(side_effect=lambda r: added.append(r))

        config: dict[str, Any] = {
            "configurable": {
                "sandbox_manager": mgr,
                "test_result_store": result_store,
            }
        }

        with (
            patch(f"{_STAGE}.mark_running", new_callable=AsyncMock),
            patch(f"{_STAGE}.mark_completed", new_callable=AsyncMock),
            patch(f"{_STAGE}.append_log", new_callable=AsyncMock),
            _patch_discovery("make test"),
        ):
            result = await run_tests(state, config)

        assert result["agent_outputs"][0]["verdict"] == "passed"
        assert len(added) == 1
        assert added[0].verdict.value == "passed"
