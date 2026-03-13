"""Sandbox failure mode tests — verify graceful handling of container errors.

These reproduce real failure scenarios: OOM, timeouts, PID exhaustion,
disk full, bad commands, destroyed containers, and network issues.

Run: pytest tests/integration/sandbox/test_failure_modes.py -v --run-sandbox
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lintel.contracts.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
)

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager

pytestmark = pytest.mark.usefixtures("_check_sandbox_prereqs")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _exec(
    mgr: SandboxManager,
    sandbox_id: str,
    command: str,
    timeout: int = 10,
) -> object:
    from lintel.contracts.types import SandboxJob

    return await mgr.execute(sandbox_id, SandboxJob(command=command, timeout_seconds=timeout))


# ---------------------------------------------------------------------------
# Command failures
# ---------------------------------------------------------------------------


async def test_nonzero_exit_code_reported(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Commands that fail should report the exit code and stderr."""
    mgr, sandbox_id = sandbox
    result = await _exec(mgr, sandbox_id, "ls /nonexistent/path 2>&1")
    assert result.exit_code != 0


async def test_syntax_error_in_command(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Shell syntax errors should be captured, not crash the sandbox."""
    mgr, sandbox_id = sandbox
    result = await _exec(mgr, sandbox_id, "if then else fi")
    assert result.exit_code != 0
    assert result.stderr or result.stdout  # error message captured


async def test_command_with_binary_output(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Binary output should be decoded with replacement, not crash."""
    mgr, sandbox_id = sandbox
    result = await _exec(mgr, sandbox_id, "head -c 100 /dev/urandom")
    assert result.exit_code == 0
    # Should have some content (may contain replacement chars)
    assert len(result.stdout) > 0


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


async def test_command_timeout(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Commands exceeding timeout should raise SandboxTimeoutError."""
    mgr, sandbox_id = sandbox
    with pytest.raises(SandboxTimeoutError):
        await _exec(mgr, sandbox_id, "sleep 30", timeout=2)


async def test_container_survives_timeout(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """After a timeout, the container should still be usable."""
    mgr, sandbox_id = sandbox
    with pytest.raises(SandboxTimeoutError):
        await _exec(mgr, sandbox_id, "sleep 30", timeout=2)

    # Container should still work
    result = await _exec(mgr, sandbox_id, "echo alive")
    assert result.exit_code == 0
    assert "alive" in result.stdout


# ---------------------------------------------------------------------------
# Container lifecycle errors
# ---------------------------------------------------------------------------


async def test_destroyed_container_raises(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Using a destroyed container should raise SandboxNotFoundError."""
    mgr, sandbox_id = sandbox
    await mgr.destroy(sandbox_id)

    with pytest.raises(SandboxNotFoundError):
        await _exec(mgr, sandbox_id, "echo hello")


async def test_invalid_sandbox_id_raises(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Using a bogus sandbox ID should raise SandboxNotFoundError."""
    mgr, _ = sandbox
    with pytest.raises(SandboxNotFoundError):
        await _exec(mgr, "bogus-id-12345", "echo hello")


async def test_double_destroy_is_safe(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Destroying an already-destroyed container should not raise."""
    mgr, sandbox_id = sandbox
    await mgr.destroy(sandbox_id)
    # Second destroy should be a no-op
    await mgr.destroy(sandbox_id)


# ---------------------------------------------------------------------------
# Resource exhaustion
# ---------------------------------------------------------------------------


async def test_pid_exhaustion_handled(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Fork bomb should be stopped by PID limit, not crash the container."""
    mgr, sandbox_id = sandbox
    # Try to fork many processes — pids_limit=256 should stop this
    await _exec(
        mgr,
        sandbox_id,
        "for i in $(seq 1 300); do sleep 60 & done 2>&1; echo DONE",
        timeout=15,
    )
    # Command should complete (some forks will fail due to PID limit)
    # The container itself should survive
    alive = await _exec(mgr, sandbox_id, "echo alive")
    assert alive.exit_code == 0
    assert "alive" in alive.stdout


async def test_tmpfs_full_reported(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Filling /tmp should produce an error, not crash the container."""
    mgr, sandbox_id = sandbox
    # /tmp is 200m tmpfs — try to write 250m
    result = await _exec(
        mgr,
        sandbox_id,
        "dd if=/dev/zero of=/tmp/bigfile bs=1M count=250 2>&1; echo EXIT=$?",
        timeout=30,
    )
    # dd should fail (no space left)
    no_space = "No space left" in result.stdout or "No space left" in result.stderr
    assert no_space or result.exit_code != 0

    # Container should still work
    alive = await _exec(mgr, sandbox_id, "rm -f /tmp/bigfile && echo alive")
    assert "alive" in alive.stdout


async def test_large_output_handled(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Commands producing huge stdout should not crash."""
    mgr, sandbox_id = sandbox
    # Generate ~5MB of output
    result = await _exec(
        mgr,
        sandbox_id,
        "yes 'aaaaaaaaaa' | head -c 5000000",
        timeout=15,
    )
    assert result.exit_code == 0
    assert len(result.stdout) > 100000  # at least some captured


# ---------------------------------------------------------------------------
# File operation errors
# ---------------------------------------------------------------------------


async def test_read_nonexistent_file_raises(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Reading a file that doesn't exist should raise SandboxExecutionError."""
    mgr, sandbox_id = sandbox
    with pytest.raises(SandboxExecutionError):
        await mgr.read_file(sandbox_id, "/workspace/does_not_exist.txt")


async def test_write_to_readonly_path_raises(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Writing to a read-only path should raise SandboxExecutionError."""
    mgr, sandbox_id = sandbox
    # /proc is read-only in containers
    with pytest.raises(SandboxExecutionError):
        await mgr.write_file(sandbox_id, "/proc/test_file", "content")


async def test_list_nonexistent_dir_raises(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Listing a nonexistent directory should raise SandboxExecutionError."""
    mgr, sandbox_id = sandbox
    with pytest.raises(SandboxExecutionError):
        await mgr.list_files(sandbox_id, "/nonexistent_dir")


# ---------------------------------------------------------------------------
# Network failures
# ---------------------------------------------------------------------------


async def test_network_disconnect_blocks_egress(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """After network disconnect, external requests should fail."""
    mgr, sandbox_id = sandbox
    await mgr.disconnect_network(sandbox_id)

    result = await _exec(
        mgr,
        sandbox_id,
        "curl -s --max-time 3 https://example.com 2>&1 || echo NETWORK_FAIL",
        timeout=10,
    )
    assert "NETWORK_FAIL" in result.stdout or result.exit_code != 0


async def test_network_reconnect_restores_egress(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """After reconnect, external requests should work again."""
    mgr, sandbox_id = sandbox
    await mgr.disconnect_network(sandbox_id)
    await mgr.reconnect_network(sandbox_id)

    result = await _exec(
        mgr,
        sandbox_id,
        "curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://example.com 2>&1",
        timeout=10,
    )
    # Should get a 200 or at least not NETWORK_FAIL
    assert result.exit_code == 0


async def test_double_disconnect_is_safe(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Disconnecting twice should not raise."""
    mgr, sandbox_id = sandbox
    await mgr.disconnect_network(sandbox_id)
    await mgr.disconnect_network(sandbox_id)  # should be safe


async def test_double_reconnect_is_safe(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Reconnecting when already connected should not raise."""
    mgr, sandbox_id = sandbox
    await mgr.reconnect_network(sandbox_id)
    await mgr.reconnect_network(sandbox_id)  # should be safe


# ---------------------------------------------------------------------------
# Stage-level error handling
# ---------------------------------------------------------------------------


async def test_implement_handles_sandbox_failure(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Implement node should handle sandbox errors gracefully."""
    import json

    from lintel.workflows.nodes.implement import spawn_implementation

    from tests.integration.sandbox.fake_runtime import PLAN_RESPONSE, make_fake_runtime
    from tests.integration.sandbox.test_pipeline_stages import (
        WORKDIR,
        SandboxProject,
        StageRunner,
    )

    mgr, sandbox_id = sandbox
    proj = SandboxProject(mgr, sandbox_id)
    await proj.setup()

    runtime = make_fake_runtime(WORKDIR)
    runner = StageRunner(proj, runtime)

    plan = json.loads(PLAN_RESPONSE)
    state = runner.state(plan=plan)

    # Destroy the sandbox before implement runs
    await mgr.destroy(sandbox_id)

    # Implement should handle the error, not crash
    result = await spawn_implementation(state, runner.config)
    # Should report error state
    assert result.get("error") or result.get("current_phase") in (
        "closed",
        "implement_failed",
    )


async def test_test_node_handles_missing_sandbox(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Test node should handle missing sandbox gracefully."""
    from lintel.workflows.nodes.test_code import run_tests

    from tests.integration.sandbox.test_pipeline_stages import SandboxProject, StageRunner

    mgr, sandbox_id = sandbox

    proj = SandboxProject(mgr, sandbox_id)
    runner = StageRunner(proj)

    # Use a bogus sandbox_id
    state = runner.state(sandbox_id="bogus-id")
    result = await run_tests(state, runner.config)

    # Should handle gracefully
    outputs = result.get("agent_outputs", [])
    assert len(outputs) > 0


async def test_review_handles_empty_diff(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Review node should handle projects with no changes gracefully."""
    from lintel.workflows.nodes.review import review_output

    from tests.integration.sandbox.fake_runtime import make_fake_runtime
    from tests.integration.sandbox.test_pipeline_stages import (
        WORKDIR,
        SandboxProject,
        StageRunner,
    )

    mgr, sandbox_id = sandbox
    proj = SandboxProject(mgr, sandbox_id)
    await proj.setup()

    runtime = make_fake_runtime(WORKDIR)
    runner = StageRunner(proj, runtime)

    # No changes made — diff will be empty
    result = await review_output(runner.state(), runner.config)

    assert result["current_phase"] == "awaiting_pr_approval"
    # Should approve (no changes to review)
    assert result["agent_outputs"][0]["verdict"] == "approve"
