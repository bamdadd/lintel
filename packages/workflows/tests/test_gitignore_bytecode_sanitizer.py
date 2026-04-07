"""Tests for ensure_gitignore_excludes_bytecode helper.

Verifies that the helper:
- adds missing bytecode patterns to .gitignore
- skips the file when all patterns are already present
- always attempts to untrack existing bytecode files when patterns are added
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes._git_helpers import (
    _BYTECODE_GITIGNORE_ENTRIES,
    ensure_gitignore_excludes_bytecode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sandbox_manager(cat_output: str = "") -> MagicMock:
    """Return a fake SandboxManager whose execute returns configurable output."""
    manager = MagicMock()

    async def _execute(sandbox_id: str, job: Any) -> MagicMock:  # noqa: ANN401
        result = MagicMock()
        cmd: str = job.command
        if cmd.startswith("cat ") and ".gitignore" in cmd:
            result.stdout = cat_output
        else:
            result.stdout = ""
        result.exit_code = 0
        return result

    manager.execute = AsyncMock(side_effect=_execute)
    return manager


# ---------------------------------------------------------------------------
# Tests — patterns appended when .gitignore is empty / absent
# ---------------------------------------------------------------------------


async def test_appends_all_patterns_when_gitignore_empty() -> None:
    """All bytecode entries must be appended if .gitignore is empty."""
    manager = _make_sandbox_manager(cat_output="")
    await ensure_gitignore_excludes_bytecode(manager, "sb-1", "/workspace/repo")

    calls = [str(c) for c in manager.execute.call_args_list]
    # The append command must have been called (at least one call containing printf)
    assert any("printf" in c for c in calls), "Expected printf/append command"
    # The untrack command must have been called
    assert any("git rm" in c for c in calls), "Expected git rm --cached command"


async def test_no_changes_when_all_patterns_present() -> None:
    """Helper must be a no-op when .gitignore already contains all patterns."""
    existing = "\n".join(_BYTECODE_GITIGNORE_ENTRIES) + "\n"
    manager = _make_sandbox_manager(cat_output=existing)

    await ensure_gitignore_excludes_bytecode(manager, "sb-1", "/workspace/repo")

    # Only the initial cat read should have been executed — no append, no git rm
    assert manager.execute.call_count == 1, (
        f"Expected only 1 execute call (cat), got {manager.execute.call_count}"
    )


async def test_appends_only_missing_patterns() -> None:
    """Helper appends only the entries that are not yet in .gitignore."""
    # Provide a .gitignore that already has __pycache__/ but not the *.pyc patterns
    partial = "__pycache__/\n"
    manager = _make_sandbox_manager(cat_output=partial)

    await ensure_gitignore_excludes_bytecode(manager, "sb-1", "/workspace/repo")

    calls = [str(c) for c in manager.execute.call_args_list]
    # append call must reference at least one missing entry (*.pyc)
    append_calls = [c for c in calls if "printf" in c]
    assert append_calls, "Expected at least one printf/append call"
    assert "*.pyc" in append_calls[0], "*.pyc should be in the append command"
    # __pycache__/ is already present — must not be re-added
    assert append_calls[0].count("__pycache__") == 0, (
        "__pycache__/ must not be re-appended when already present"
    )


# ---------------------------------------------------------------------------
# Tests — git rm command targets correct workdir
# ---------------------------------------------------------------------------


async def test_git_rm_uses_correct_workdir() -> None:
    """git rm --cached must be run inside the supplied workdir."""
    manager = _make_sandbox_manager(cat_output="")
    await ensure_gitignore_excludes_bytecode(manager, "sb-42", "/repo/path")

    calls = [str(c) for c in manager.execute.call_args_list]
    git_rm_calls = [c for c in calls if "git rm" in c]
    assert git_rm_calls, "Expected a git rm call"
    assert "/repo/path" in git_rm_calls[0], "git rm must cd into the correct workdir"


# ---------------------------------------------------------------------------
# Tests — graceful handling of sandbox_id passed through
# ---------------------------------------------------------------------------


async def test_correct_sandbox_id_passed_to_execute() -> None:
    """SandboxManager.execute must always receive the provided sandbox_id."""
    manager = _make_sandbox_manager(cat_output="")
    await ensure_gitignore_excludes_bytecode(manager, "my-sandbox-id", "/workspace")

    for c in manager.execute.call_args_list:
        positional_args = c.args
        assert positional_args[0] == "my-sandbox-id", (
            f"Wrong sandbox_id in execute call: {positional_args}"
        )
