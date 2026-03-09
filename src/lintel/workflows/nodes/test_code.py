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

    # Discover how to run tests
    test_command = await _discover_test_command(
        sandbox_manager,
        sandbox_id,
        workdir,
        _config,
        state,
    )

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


async def _discover_test_command(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    config: Mapping[str, Any],
    state: ThreadWorkflowState,
) -> str:
    """Discover how to run tests by inspecting the project structure.

    Strategy (in priority order):
    1. Makefile with a test-like target → use `make <target>`
    2. package.json with "test" script → `npm test`
    3. pyproject.toml → install deps + `uv run python -m pytest`
    4. Cargo.toml → `cargo test`
    5. go.mod → `go test ./...`
    6. Fallback → echo message
    """
    from lintel.contracts.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import append_log

    await append_log(config, "test", "Discovering test command...", state)

    # Check what files exist in the project root
    detect_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                f"ls {workdir}/Makefile {workdir}/pyproject.toml "
                f"{workdir}/package.json {workdir}/Cargo.toml {workdir}/go.mod "
                "2>/dev/null || true"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    files = detect_result.stdout.strip()

    # 1. Makefile — parse targets for test-related ones
    if "Makefile" in files:
        test_target = await _find_make_test_target(sandbox_manager, sandbox_id, workdir)
        if test_target:
            await append_log(config, "test", f"Found Makefile target: {test_target}", state)
            # If the project also has pyproject.toml, ensure deps are installed first
            if "pyproject.toml" in files:
                await _ensure_python_deps(sandbox_manager, sandbox_id, workdir, config, state)
            return f"make {test_target}"

    # 2. package.json — check for test script
    if "package.json" in files:
        has_test = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"grep -q '\"test\"' {workdir}/package.json && echo HAS_TEST || true",
                workdir=workdir,
                timeout_seconds=5,
            ),
        )
        if "HAS_TEST" in has_test.stdout:
            await append_log(config, "test", "Found npm test script", state)
            return "npm test"

    # 3. pyproject.toml — Python project
    if "pyproject.toml" in files:
        await _ensure_python_deps(sandbox_manager, sandbox_id, workdir, config, state)
        await append_log(config, "test", "Using pytest for Python project", state)
        return 'export PATH="$HOME/.local/bin:$PATH" && uv run python -m pytest'

    # 4. Cargo.toml — Rust project
    if "Cargo.toml" in files:
        await append_log(config, "test", "Using cargo test for Rust project", state)
        return "cargo test"

    # 5. go.mod — Go project
    if "go.mod" in files:
        await append_log(config, "test", "Using go test for Go project", state)
        return "go test ./..."

    await append_log(config, "test", "No test runner detected", state)
    return "echo 'No test runner detected'"


async def _find_make_test_target(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> str | None:
    """Parse Makefile for a test-related target, preferring `make help` output."""
    from lintel.contracts.types import SandboxJob

    # Try `make help` first — many projects document their targets
    help_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(command="make help 2>/dev/null || true", workdir=workdir, timeout_seconds=10),
    )
    help_output = help_result.stdout.lower()

    # Look for test targets in help output (prefer `test` over `test-unit` etc.)
    # Common patterns: "test", "test-all", "test-unit", "check", "verify"
    if help_output.strip():
        return _pick_test_target_from_output(help_output)

    # Fallback: parse Makefile directly for target names
    targets_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                f"grep -E '^[a-zA-Z_-]+:' {workdir}/Makefile "
                "| sed 's/:.*//' | sort -u 2>/dev/null || true"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    targets_output = targets_result.stdout.lower()
    if targets_output.strip():
        return _pick_test_target_from_output(targets_output)

    return None


def _pick_test_target_from_output(output: str) -> str | None:
    """Pick the best test target from make help or target list output.

    Priority: 'test' > 'test-all' > 'all' > 'check' > 'test-unit' > 'verify'
    Only matches the first token on each line (the target name), not descriptions.
    """
    # Extract first token from each line — that's the target name
    targets: set[str] = set()
    for line in output.lower().strip().split("\n"):
        tokens = line.split()
        if tokens:
            targets.add(tokens[0])

    preferred = ("test", "test-all", "all", "check", "test-unit", "verify")
    for candidate in preferred:
        if candidate in targets:
            return candidate
    return None


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
