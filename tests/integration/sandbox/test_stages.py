"""Stage-level integration tests — run individual workflow nodes against real sandboxes.

These validate the full chain: sandbox creation -> file transfer -> command execution
-> result parsing, without needing LLM calls or full pipeline orchestration.

Run: pytest tests/integration/sandbox/test_stages.py -v --run-sandbox
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from lintel.sandbox.protocols import SandboxManager

pytestmark = pytest.mark.usefixtures("_check_sandbox_prereqs")

FIXTURE_PROJECT = Path(__file__).parent.parent.parent / "fixtures" / "sample-python-project"


async def _copy_fixture_to_sandbox(
    mgr: SandboxManager,
    sandbox_id: str,
    workdir: str = "/workspace/repo",
) -> None:
    """Copy the fixture project into the sandbox and init a git repo."""
    from lintel.sandbox.types import SandboxJob

    await mgr.execute(
        sandbox_id,
        SandboxJob(command=f"mkdir -p {workdir}", timeout_seconds=10),
    )

    for root, _dirs, files in os.walk(FIXTURE_PROJECT):
        for fname in files:
            local_path = Path(root) / fname
            rel = local_path.relative_to(FIXTURE_PROJECT)
            remote_path = f"{workdir}/{rel}"
            content = local_path.read_text()
            await mgr.write_file(sandbox_id, remote_path, content)

    await mgr.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "git init && git add -A"
                " && git -c user.name=test -c user.email=test@test commit -m init"
            ),
            workdir=workdir,
            timeout_seconds=30,
        ),
    )


async def test_discover_test_command(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """discover_test_command should find the Makefile test-unit target."""
    from lintel.skills.discover_test_command import discover_test_command

    mgr, sandbox_id = sandbox
    workdir = "/workspace/repo"
    await _copy_fixture_to_sandbox(mgr, sandbox_id, workdir)

    result = await discover_test_command(mgr, sandbox_id, workdir)

    assert "test_command" in result
    assert "make" in result["test_command"] or "pytest" in result["test_command"]


async def test_run_tests_with_fixture_project(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """Full test stage: discover -> setup -> run tests -> parse results."""
    from lintel.sandbox.types import SandboxJob
    from lintel.skills.discover_test_command import discover_test_command

    mgr, sandbox_id = sandbox
    workdir = "/workspace/repo"
    await _copy_fixture_to_sandbox(mgr, sandbox_id, workdir)

    # Install deps
    await mgr.execute(
        sandbox_id,
        SandboxJob(
            command=('export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -5'),
            workdir=workdir,
            timeout_seconds=120,
        ),
    )

    discovery = await discover_test_command(mgr, sandbox_id, workdir)
    test_cmd = discovery["test_command"]

    result = await mgr.execute(
        sandbox_id,
        SandboxJob(command=test_cmd, workdir=workdir, timeout_seconds=120),
    )

    assert result.exit_code == 0, f"Tests failed:\n{result.stdout}\n{result.stderr}"
    assert "passed" in result.stdout.lower()


async def test_collect_artifacts_returns_diff(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """collect_artifacts should return a diff after file changes."""
    mgr, sandbox_id = sandbox
    workdir = "/workspace/repo"
    await _copy_fixture_to_sandbox(mgr, sandbox_id, workdir)

    new_content = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n\n"
        "def multiply(a: int, b: int) -> int:\n"
        "    return a * b\n"
    )
    await mgr.write_file(sandbox_id, f"{workdir}/src/math_utils.py", new_content)

    artifacts = await mgr.collect_artifacts(sandbox_id, workdir)

    assert artifacts["type"] == "diff"
    assert artifacts["exit_code"] == 0
    assert (
        "multiply" in artifacts["content"]
    ), f"Diff should contain the new function. Got:\n{artifacts['content'][:500]}"


async def test_collect_artifacts_excludes_lock_files(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """collect_artifacts should not include lock file noise."""
    mgr, sandbox_id = sandbox
    workdir = "/workspace/repo"
    await _copy_fixture_to_sandbox(mgr, sandbox_id, workdir)

    await mgr.write_file(sandbox_id, f"{workdir}/uv.lock", "fake lock content\n")
    await mgr.write_file(sandbox_id, f"{workdir}/src/new_file.py", "x = 1\n")

    artifacts = await mgr.collect_artifacts(sandbox_id, workdir)

    assert "new_file.py" in artifacts["content"]
    assert "uv.lock" not in artifacts["content"], "Lock files should be excluded from diff"


async def test_pytest_parallelism_respects_cpu_limit(
    sandbox: tuple[SandboxManager, str],
) -> None:
    """pytest -n auto should use the container's CPU count, not the host's."""
    from lintel.sandbox.types import SandboxJob

    mgr, sandbox_id = sandbox
    workdir = "/workspace/repo"
    await _copy_fixture_to_sandbox(mgr, sandbox_id, workdir)

    await mgr.execute(
        sandbox_id,
        SandboxJob(
            command=('export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -3'),
            workdir=workdir,
            timeout_seconds=120,
        ),
    )

    result = await mgr.execute(
        sandbox_id,
        SandboxJob(
            command=(
                'export PATH="$HOME/.local/bin:$PATH" && uv run pytest tests/ -v -n auto 2>&1'
            ),
            workdir=workdir,
            timeout_seconds=120,
        ),
    )

    assert result.exit_code == 0, f"Tests failed:\n{result.stdout}\n{result.stderr}"
    for line in result.stdout.split("\n"):
        if "workers" in line and "created" in line.lower():
            parts = line.split("created:")[1].strip().split("/")
            worker_count = int(parts[0].strip())
            assert (
                worker_count <= 4
            ), f"pytest -n auto spawned {worker_count} workers, expected <=4 for a 2-CPU sandbox"
            break
