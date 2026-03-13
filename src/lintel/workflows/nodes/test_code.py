"""Test execution workflow node — runs tests in sandbox.

Uses the ``skill_discover_test_command`` skill to determine *how* to run
tests for the project.  Projects can register a custom version of the
skill to override discovery logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)


async def run_tests(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Run the project test suite in the sandbox and report results."""
    from lintel.contracts.types import SandboxJob
    from lintel.skills.discover_test_command import discover_test_command
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        mark_completed,
        mark_running,
    )

    _config = config or {}
    sandbox_manager: SandboxManager | None = _config.get("configurable", {}).get("sandbox_manager")

    # Fall back to runtime registry after LangGraph interrupt/resume
    run_id = state.get("run_id", "")
    if sandbox_manager is None and run_id:
        from lintel.workflows.nodes._runtime_registry import get_sandbox_manager

        sandbox_manager = get_sandbox_manager(run_id)

    await mark_running(_config, "test", state)

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id or sandbox_manager is None:
        logger.warning("test_skipped_no_sandbox")
        await mark_completed(_config, "test", state, error="No sandbox available")
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
    await append_log(_config, "test", "Discovering test command...", state)
    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workdir)
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        logger.exception("test_discovery_failed")
        await mark_completed(
            _config, "test", state, error="Test discovery failed — sandbox unavailable"
        )
        return await handle_node_error(
            state, "test", Exception("Test discovery failed — sandbox unavailable")
        )
    test_command = discovery["test_command"]
    setup_commands: list[str] = discovery.get("setup_commands", [])

    # Run setup commands (dep install, etc.)
    for cmd in setup_commands:
        await append_log(_config, "test", f"Setup: {cmd[:80]}", state)
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=cmd, workdir=workdir, timeout_seconds=180),
        )

    # Try to run only changed test files first (much faster than full suite)
    changed_test_cmd = await _build_changed_tests_command(
        sandbox_manager,
        sandbox_id,
        workdir,
    )
    if changed_test_cmd:
        test_command = changed_test_cmd
        await append_log(
            _config,
            "test",
            f"Running changed tests: {test_command[:80]}",
            state,
        )
    else:
        await append_log(_config, "test", f"Running: {test_command}", state)
    try:
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=test_command,
                workdir=workdir,
                timeout_seconds=600,
            ),
        )
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        logger.exception("test_sandbox_execute_failed")
        await mark_completed(
            _config,
            "test",
            state,
            error="Sandbox execution failed",
        )
        return await handle_node_error(
            state,
            "test",
            Exception("Sandbox execution failed"),
        )

    passed = result.exit_code == 0
    verdict = "passed" if passed else "failed"
    output = result.stdout + result.stderr

    # Log test output to stage
    await append_log(_config, "test", f"Exit code: {result.exit_code}", state)
    for line in output.strip().split("\n")[:30]:
        await append_log(_config, "test", line, state)

    # Truncate long output
    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    logger.info(
        "test_run_complete verdict=%s exit_code=%d",
        verdict,
        result.exit_code,
    )

    # Persist test result
    test_result_store = _config.get("configurable", {}).get("test_result_store")
    if test_result_store is not None:
        from uuid import uuid4

        from lintel.contracts.types import TestResult, TestVerdict

        test_result_record = TestResult(
            result_id=str(uuid4()),
            run_id=state.get("run_id", ""),
            stage_id="test",
            verdict=TestVerdict.PASSED if passed else TestVerdict.FAILED,
            output=output[:5000],
            failures=tuple(output.split("\n")[:10]) if not passed else (),
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

    await mark_completed(
        _config,
        "test",
        state,
        error="" if passed else f"Tests failed (exit {result.exit_code})",
    )
    return {
        "current_phase": "reviewing",
        "agent_outputs": [
            {
                "node": "test",
                "verdict": verdict,
                "exit_code": result.exit_code,
                "summary": (
                    f"Tests {verdict}" + (f": {result.stderr[:200]}" if not passed else "")
                ),
                "output": output,
            }
        ],
    }


async def _build_changed_tests_command(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> str | None:
    """Find test files for changed code and build a targeted pytest command.

    Looks at both changed test files AND changed source files (mapping
    src/foo/bar.py → tests/**/test_bar.py) so that the test run covers
    code the LLM actually touched rather than the entire suite.

    Returns a pytest command or None (falls back to full suite).
    """
    from lintel.contracts.types import SandboxJob

    # 1. Find ALL changed files vs main
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "{ git diff --name-only origin/main 2>/dev/null"
                " || git diff --name-only main 2>/dev/null"
                " || git diff --name-only HEAD~1 2>/dev/null; }"
                " | sort -u || true"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    all_changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    if not all_changed:
        return None

    # 2. Collect changed test files directly
    test_files: set[str] = set()
    source_basenames: set[str] = set()
    for f in all_changed:
        if "/test_" in f and f.endswith(".py"):
            test_files.add(f)
        elif f.endswith(".py") and "/tests/" not in f:
            # Extract basename: src/lintel/domain/foo.py → foo
            import os

            basename = os.path.splitext(os.path.basename(f))[0]
            if basename != "__init__":
                source_basenames.add(basename)

    # 3. Find corresponding test files for changed source files
    if source_basenames:
        # Build a find command to locate test files matching changed sources
        patterns = " -o ".join(f'-name "test_{b}.py"' for b in source_basenames)
        find_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"find tests/ -type f \\( {patterns} \\) 2>/dev/null || true",
                workdir=workdir,
                timeout_seconds=10,
            ),
        )
        for f in find_result.stdout.strip().split("\n"):
            if f.strip():
                test_files.add(f.strip())

    if not test_files:
        return None

    path_prefix = 'export PATH="$HOME/.local/bin:$PATH"'
    files_arg = " ".join(sorted(test_files))
    logger.info(
        "test_discovery: running %d targeted test files instead of full suite",
        len(test_files),
    )
    return f"{path_prefix} && uv run python -m pytest {files_arg} -v 2>&1"
