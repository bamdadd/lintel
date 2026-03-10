"""Sandbox smoke tests — validate container config without running workflows.

Fast (<30s) checks that catch issues like the CPU oversubscription bug
where -n auto spawned 16 workers in a 2-CPU container.

Run: pytest tests/integration/sandbox/test_smoke.py -v --run-sandbox
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager
    from lintel.contracts.types import SandboxResult

pytestmark = pytest.mark.usefixtures("_check_sandbox_prereqs")


async def _exec(
    sandbox: tuple[SandboxManager, str],
    command: str,
) -> SandboxResult:
    from lintel.contracts.types import SandboxJob

    mgr, sandbox_id = sandbox
    return await mgr.execute(
        sandbox_id,
        SandboxJob(command=command, timeout_seconds=10),
    )


async def test_cpu_affinity_matches_quota(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """sched_getaffinity inside the container should match the configured quota.

    pytest-xdist uses sched_getaffinity (not os.cpu_count) to determine
    worker count for -n auto. cpuset_cpus controls this.
    """
    from lintel.contracts.types import SandboxConfig

    expected_cpus = SandboxConfig().cpu_quota // 100000

    result = await _exec(
        sandbox,
        "python3 -c 'import os; print(len(os.sched_getaffinity(0)))'",
    )
    assert result.exit_code == 0
    actual_cpus = int(result.stdout.strip())
    assert actual_cpus == expected_cpus, (
        f"Container sched_getaffinity reports {actual_cpus} CPUs but quota allows "
        f"{expected_cpus}. pytest -n auto will oversubscribe."
    )


async def test_memory_limit_applied(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Container should report the configured memory limit."""
    result = await _exec(
        sandbox,
        "cat /sys/fs/cgroup/memory.max 2>/dev/null"
        " || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null"
        " || echo unknown",
    )
    assert result.exit_code == 0
    raw = result.stdout.strip()
    if raw not in ("unknown", "max"):
        limit_bytes = int(raw)
        limit_gb = limit_bytes / (1024**3)
        assert limit_gb <= 5, f"Memory limit {limit_gb:.1f}GB exceeds expected 4GB"
        assert limit_gb >= 3, f"Memory limit {limit_gb:.1f}GB is too low"


async def test_pids_limit(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Container should enforce PID limits."""
    result = await _exec(
        sandbox,
        "cat /sys/fs/cgroup/pids.max 2>/dev/null || echo unknown",
    )
    assert result.exit_code == 0
    raw = result.stdout.strip()
    if raw not in ("unknown", "max"):
        assert int(raw) <= 512, f"PID limit {raw} is too high"


async def test_tools_available(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Sandbox image should have required tools pre-installed."""
    result = await _exec(
        sandbox,
        "which python3 && which git && which uv && which node && which bun && echo OK",
    )
    assert result.exit_code == 0
    assert "OK" in result.stdout


async def test_security_caps_dropped(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Container should have all capabilities dropped."""
    result = await _exec(
        sandbox,
        "cat /proc/1/status | grep -i capeff || echo unknown",
    )
    assert result.exit_code == 0
    # All caps dropped = CapEff: 0000000000000000
    if "CapEff" in result.stdout:
        cap_hex = result.stdout.split("CapEff:")[1].strip()
        assert cap_hex == "0000000000000000", f"Container has capabilities: {cap_hex}"
