"""Test execution workflow node — runs tests in sandbox."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)

# Default test commands to try, in order of preference
DEFAULT_TEST_COMMANDS = (
    "make test",
    "pytest",
    "npm test",
    "cargo test",
    "go test ./...",
)


async def run_tests(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Run the project test suite in the sandbox and report results."""
    from lintel.contracts.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import mark_completed, mark_running

    _config = config or {}
    sandbox_manager: SandboxManager | None = _config.get("configurable", {}).get("sandbox_manager")

    await mark_running(_config, "test", state)

    test_command: str | None = None

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

    workdir = "/workspace/repo"

    # Determine which test command to run
    if test_command is None:
        # Auto-detect by checking which files exist
        detect_cmd = (
            f"ls {workdir}/Makefile {workdir}/pytest.ini "
            f"{workdir}/pyproject.toml {workdir}/package.json "
            f"{workdir}/Cargo.toml {workdir}/go.mod "
            "2>/dev/null || true"
        )
        detect_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=detect_cmd, workdir=workdir, timeout_seconds=10),
        )
        files = detect_result.stdout.strip()
        if "Makefile" in files:
            test_command = "make test"
        elif "pyproject.toml" in files or "pytest.ini" in files:
            test_command = "pytest"
        elif "package.json" in files:
            test_command = "npm test"
        elif "Cargo.toml" in files:
            test_command = "cargo test"
        elif "go.mod" in files:
            test_command = "go test ./..."
        else:
            test_command = "echo 'No test runner detected'"

    try:
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=test_command, workdir=workdir, timeout_seconds=300),
        )
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        logger.exception("test_sandbox_execute_failed")
        await mark_completed(_config, "test", state, error="Sandbox execution failed")
        return await handle_node_error(state, "test", Exception("Sandbox execution failed"))

    passed = result.exit_code == 0
    verdict = "passed" if passed else "failed"
    output = result.stdout + result.stderr

    # Truncate long output
    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    logger.info("test_run_complete", verdict=verdict, exit_code=result.exit_code)

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
                "summary": f"Tests {verdict}" + (f": {result.stderr[:200]}" if not passed else ""),
                "output": output,
            }
        ],
    }
