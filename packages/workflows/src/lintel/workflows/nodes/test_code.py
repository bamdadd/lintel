"""Test execution workflow node — runs tests in sandbox.

Uses the ``skill_discover_test_command`` skill to determine *how* to run
tests for the project.  Projects can register a custom version of the
skill to override discovery logic.

Selective execution: when changed files are detected, only the affected
test files are run (much faster than the full suite).  Per-module verdicts
are included in the output.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)


async def run_tests(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Run the project test suite in the sandbox and report results."""
    from lintel.domain.skills.discover_test_command import discover_test_command
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._affected_tests import (
        build_pytest_command,
        parse_test_results_per_module,
        select_affected_tests,
    )
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config, state)
    sandbox_manager: SandboxManager | None = _config.get("configurable", {}).get("sandbox_manager")

    # Fall back to runtime registry after LangGraph interrupt/resume
    run_id = state.get("run_id", "")
    if sandbox_manager is None and run_id:
        from lintel.workflows.nodes._runtime_registry import get_sandbox_manager

        sandbox_manager = get_sandbox_manager(run_id)

    await tracker.mark_running("test")

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id or sandbox_manager is None:
        logger.warning("test_skipped_no_sandbox")
        await tracker.mark_completed("test", error="No sandbox available")
        return {
            "current_phase": "reviewing",
            "agent_outputs": [
                {"node": "test", "verdict": "skipped", "summary": "No sandbox available"}
            ],
        }

    workdir = state.get("workspace_path", "/workspace/repo")

    # Reconnect network for dependency installation and test execution
    try:
        await sandbox_manager.reconnect_network(sandbox_id)
    except Exception:
        logger.warning("test_reconnect_network_failed")

    # Discover how to run tests via skill
    await tracker.append_log("test", "Discovering test command...")
    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workdir)
    except Exception:
        from lintel.workflows.nodes._error_handling import WorkflowErrorHandler

        logger.exception("test_discovery_failed")
        await tracker.mark_completed("test", error="Test discovery failed — sandbox unavailable")
        return await WorkflowErrorHandler.handle(
            state, "test", Exception("Test discovery failed — sandbox unavailable")
        )
    test_command = discovery["test_command"]
    setup_commands: list[str] = discovery.get("setup_commands", [])

    # Run setup commands (dep install, etc.)
    for cmd in setup_commands:
        await tracker.append_log("test", f"Setup: {cmd[:80]}")
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=cmd, workdir=workdir, timeout_seconds=180),
        )

    # --- Selective test execution: run only affected tests when possible ---
    base_branch = state.get("repo_branch", "main")
    affected = await select_affected_tests(sandbox_manager, sandbox_id, workdir, base_branch)
    targeted_cmd = build_pytest_command(affected.test_files)
    used_selective = False
    if targeted_cmd:
        test_command = targeted_cmd
        used_selective = True
        await tracker.append_log(
            "test",
            f"Selective: running {len(affected.test_files)} affected test files",
        )
    else:
        await tracker.append_log("test", f"Running full suite: {test_command}")

    async def _log_test_line(line: str) -> None:
        await tracker.append_log("test", line)

    try:
        from lintel.workflows.nodes.implement import _stream_execute_with_logging

        output, exit_code = await _stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            test_command,
            workdir,
            600,
            _log_test_line,
        )
    except Exception:
        from lintel.workflows.nodes._error_handling import WorkflowErrorHandler

        logger.exception("test_sandbox_execute_failed")
        await tracker.mark_completed(
            "test",
            error="Sandbox execution failed",
        )
        return await WorkflowErrorHandler.handle(
            state,
            "test",
            Exception("Sandbox execution failed"),
        )

    passed = exit_code == 0
    verdict = "passed" if passed else "failed"

    await tracker.append_log("test", f"Exit code: {exit_code}")

    # Parse per-module verdicts for structured reporting
    module_verdicts = parse_test_results_per_module(output)

    # Truncate long output
    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    logger.info(
        "test_run_complete verdict=%s exit_code=%d selective=%s affected=%d",
        verdict,
        exit_code,
        used_selective,
        len(affected.test_files),
    )

    # Persist test result
    test_result_store = _config.get("configurable", {}).get("test_result_store")
    if test_result_store is not None:
        from uuid import uuid4

        from lintel.domain.types import TestResult, TestVerdict

        test_result_record = TestResult(
            result_id=str(uuid4()),
            run_id=state.get("run_id", ""),
            stage_id="test",
            verdict=TestVerdict.PASSED if passed else TestVerdict.FAILED,
            output=output[:5000],
            failures=tuple(f for f, v in module_verdicts.items() if v == "failed")
            if module_verdicts
            else (tuple(output.split("\n")[:10]) if not passed else ()),
        )
        try:
            await test_result_store.add(test_result_record)
        except Exception:
            logger.warning("test_result_persist_failed")

    # Disconnect network after test execution
    try:
        await sandbox_manager.disconnect_network(sandbox_id)
    except Exception:
        logger.warning("test_disconnect_network_failed")

    await tracker.mark_completed(
        "test",
        error="" if passed else f"Tests failed (exit {exit_code})",
    )
    return {
        "current_phase": "reviewing",
        "agent_outputs": [
            {
                "node": "test",
                "verdict": verdict,
                "exit_code": exit_code,
                "selective": used_selective,
                "affected_test_files": len(affected.test_files),
                "module_verdicts": module_verdicts,
                "summary": (
                    f"Tests {verdict}"
                    + (f" (exit {exit_code})" if not passed else "")
                    + (f" [{len(affected.test_files)} affected files]" if used_selective else "")
                ),
                "output": output,
            }
        ],
    }
