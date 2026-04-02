"""Selective test execution — detect changed files and map them to test files.

Provides a shared ``select_affected_tests`` function used by both
the standalone test node (``test_code.py``) and the TDD implement loop
(``_impl_discovery.py``) to run only tests covering agent-changed code.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.sandbox.protocols import SandboxManager

logger = logging.getLogger(__name__)


def _is_test_file(path: str) -> bool:
    """Return True if *path* looks like a pytest test file."""
    return path.endswith(".py") and ("/test_" in path or path.startswith("test_"))


# Git command that collects all changed files vs the base branch.
# Combines committed diffs, uncommitted changes, and untracked files.
_GIT_CHANGED_FILES_CMD = (
    "{{ git diff --name-only origin/{base} 2>/dev/null;"
    " git diff --name-only {base} 2>/dev/null;"
    " git diff --name-only HEAD~1 2>/dev/null;"
    " git status --porcelain 2>/dev/null | awk '{{print $NF}}';"
    " }} | sort -u || true"
)


@dataclass(frozen=True)
class AffectedTestResult:
    """Result of the affected-test analysis."""

    changed_files: tuple[str, ...]
    test_files: tuple[str, ...]
    source_files: tuple[str, ...]


async def detect_changed_files(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    base_branch: str = "main",
) -> list[str]:
    """Return the list of files changed vs *base_branch* in the sandbox."""
    from lintel.sandbox.types import SandboxJob

    cmd = _GIT_CHANGED_FILES_CMD.format(base=base_branch)
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(command=cmd, workdir=workdir, timeout_seconds=10),
    )
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


async def select_affected_tests(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    base_branch: str = "main",
) -> AffectedTestResult:
    """Analyse changed files and return the set of affected test files.

    Strategy:
    1. Collect all changed files (committed + uncommitted + untracked).
    2. Partition into test files and source files.
    3. For each changed source file ``src/foo/bar.py``, look for
       ``tests/**/test_bar.py`` in the repo (single-package or workspace).
    4. Return both the directly-changed test files and the inferred ones.
    """
    from lintel.sandbox.types import SandboxJob

    all_changed = await detect_changed_files(sandbox_manager, sandbox_id, workdir, base_branch)
    if not all_changed:
        return AffectedTestResult(changed_files=(), test_files=(), source_files=())

    test_files: set[str] = set()
    source_files: list[str] = []
    source_basenames: set[str] = set()

    for f in all_changed:
        if _is_test_file(f):
            test_files.add(f)
        elif f.endswith(".py") and "/tests/" not in f:
            source_files.append(f)
            basename = os.path.splitext(os.path.basename(f))[0]
            if basename != "__init__":
                source_basenames.add(basename)

    # Find corresponding test files for changed source files
    if source_basenames:
        patterns = " -o ".join(f'-name "test_{b}.py"' for b in source_basenames)
        find_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"{{ find tests/ -type f \\( {patterns} \\) 2>/dev/null;"
                    f" find packages/*/tests/ -type f \\( {patterns} \\) 2>/dev/null; }}"
                    " | sort -u || true"
                ),
                workdir=workdir,
                timeout_seconds=10,
            ),
        )
        for f in find_result.stdout.strip().split("\n"):
            if f.strip():
                test_files.add(f.strip())

    logger.info(
        "affected_tests: %d changed files -> %d test files",
        len(all_changed),
        len(test_files),
    )

    return AffectedTestResult(
        changed_files=tuple(all_changed),
        test_files=tuple(sorted(test_files)),
        source_files=tuple(source_files),
    )


def build_pytest_command(test_files: tuple[str, ...]) -> str | None:
    """Build a targeted pytest command for the given test files.

    Returns ``None`` if no test files are provided (caller should fall
    back to the full test suite).
    """
    if not test_files:
        return None
    path_prefix = 'export PATH="$HOME/.local/bin:$PATH"'
    files_arg = " ".join(test_files)
    return f"{path_prefix} && uv run python -m pytest {files_arg} -v 2>&1"


def parse_test_results_per_module(
    output: str,
) -> dict[str, str]:
    """Parse pytest output into per-module pass/fail verdicts.

    Returns a dict mapping test file paths to ``"passed"`` or ``"failed"``.
    Scans for PASSED/FAILED markers in the pytest summary lines.
    """
    results: dict[str, str] = {}

    for line in output.split("\n"):
        stripped = line.strip()
        # Match "PASSED tests/test_foo.py::test_bar" or "FAILED tests/test_foo.py::test_bar"
        if stripped.startswith("PASSED ") or stripped.startswith("FAILED "):
            parts = stripped.split(" ", 1)
            if len(parts) == 2 and "::" in parts[1]:
                verdict = parts[0].lower()
                test_path = parts[1].split("::")[0]
                # Only mark as failed if any test in the module failed
                if verdict == "failed" or test_path not in results:
                    results[test_path] = verdict

    # Also parse the short test summary info section
    in_summary = False
    for line in output.split("\n"):
        stripped = line.strip()
        if "short test summary info" in stripped:
            in_summary = True
            continue
        if in_summary:
            if stripped.startswith("FAILED ") and "::" in stripped:
                test_path = stripped.split(" ", 1)[1].split("::")[0]
                results[test_path] = "failed"
            elif stripped.startswith("="):
                break

    return results
