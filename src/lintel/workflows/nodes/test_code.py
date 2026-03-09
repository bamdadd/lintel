"""Test execution workflow node — runs tests in sandbox."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    from lintel.workflows.nodes._stage_tracking import append_log, mark_completed, mark_running

    _config = config or {}
    sandbox_manager: SandboxManager | None = _config.get("configurable", {}).get("sandbox_manager")

    # Fall back to runtime registry after LangGraph interrupt/resume
    run_id = state.get("run_id", "")
    if sandbox_manager is None and run_id:
        from lintel.workflows.nodes._runtime_registry import get_sandbox_manager

        sandbox_manager = get_sandbox_manager(run_id)

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

    workdir = state.get("workspace_path", "/workspace/repo")

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

        # Install dependencies if needed (reconnect network for downloads + test execution)
        if "pyproject.toml" in files:
            try:
                await sandbox_manager.reconnect_network(sandbox_id)
            except Exception:
                logger.warning("test_reconnect_network_failed")
            await _ensure_python_deps(sandbox_manager, sandbox_id, workdir, _config, state)
            test_command = 'export PATH="$HOME/.local/bin:$PATH" && uv run python -m pytest'
        elif "package.json" in files:
            test_command = "npm test"
        elif "Cargo.toml" in files:
            test_command = "cargo test"
        elif "go.mod" in files:
            test_command = "go test ./..."
        else:
            test_command = "echo 'No test runner detected'"

    await append_log(_config, "test", f"Running: {test_command}", state)
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

    # Log test output to stage
    await append_log(_config, "test", f"Exit code: {result.exit_code}", state)
    for line in output.strip().split("\n")[:30]:
        await append_log(_config, "test", line, state)

    # Truncate long output
    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    logger.info("test_run_complete verdict=%s exit_code=%d", verdict, result.exit_code)

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
                "summary": f"Tests {verdict}" + (f": {result.stderr[:200]}" if not passed else ""),
                "output": output,
            }
        ],
    }


async def _ensure_python_deps(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    config: Mapping[str, Any],
    state: ThreadWorkflowState,
) -> None:
    """Install uv and project dependencies in the sandbox if needed."""
    from lintel.contracts.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import append_log

    # Check if uv is available
    check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="which uv 2>/dev/null || echo MISSING",
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    if "MISSING" in check.stdout:
        await append_log(config, "test", "Installing uv...", state)
        install = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command="curl -LsSf https://astral.sh/uv/install.sh | sh",
                workdir=workdir,
                timeout_seconds=60,
            ),
        )
        if install.exit_code != 0:
            logger.warning("uv_install_failed exit=%d: %s", install.exit_code, install.stderr[:200])
            await append_log(config, "test", f"uv install failed: {install.stderr[:200]}", state)
            return
        # Add uv to PATH for subsequent commands
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command="echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.bashrc",
                workdir=workdir,
                timeout_seconds=5,
            ),
        )

    # Install project dependencies
    await append_log(config, "test", "Installing Python dependencies...", state)
    sync = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command='export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -5',
            workdir=workdir,
            timeout_seconds=120,
        ),
    )
    if sync.exit_code != 0:
        logger.warning("uv_sync_failed exit=%d: %s", sync.exit_code, sync.stderr[:200])
        await append_log(config, "test", f"Dependency install failed: {sync.stderr[:200]}", state)
    else:
        await append_log(config, "test", "Dependencies installed", state)
        # Download spacy model into venv (presidio needs it at import time)
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    'export PATH="$HOME/.local/bin:$PATH" '
                    "&& uv run python -m spacy download en_core_web_sm 2>&1 | tail -3"
                ),
                workdir=workdir,
                timeout_seconds=60,
            ),
        )
