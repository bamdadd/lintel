"""Shared git helper utilities for workflow nodes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.sandbox.protocols import SandboxManager

logger = logging.getLogger(__name__)

# Bytecode patterns that should never be committed to a repository.
_BYTECODE_GITIGNORE_ENTRIES: tuple[str, ...] = (
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
)


async def ensure_gitignore_excludes_bytecode(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> None:
    """Ensure .gitignore in *workdir* contains bytecode exclusion patterns.

    This helper must be called **before** ``git add -A`` to prevent Python
    bytecode files (``__pycache__/``, ``*.pyc``, etc.) from being staged and
    committed by the implement/close workflow nodes.

    The function performs three steps:

    1. Reads the current ``.gitignore`` (empty string if absent).
    2. Appends any missing bytecode patterns.
    3. If any patterns were appended, removes already-tracked bytecode files
       from the git index with ``git rm -r --cached`` so they are not
       re-committed after the ``.gitignore`` update.
    """
    from lintel.sandbox.types import SandboxJob

    # Read current .gitignore content (ignore errors if file does not exist)
    read_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"cat {workdir}/.gitignore 2>/dev/null || true",
            timeout_seconds=10,
        ),
    )
    current_content: str = read_result.stdout or ""

    missing_entries = [
        entry for entry in _BYTECODE_GITIGNORE_ENTRIES if entry not in current_content
    ]

    if not missing_entries:
        # All required patterns already present — nothing to do.
        return

    # Append missing entries to .gitignore
    additions = "\n".join(missing_entries)
    append_cmd = (
        f"printf '\\n# Python bytecode (added by lintel)\\n{additions}\\n' >> {workdir}/.gitignore"
    )
    await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(command=append_cmd, timeout_seconds=10),
    )

    # Remove already-tracked bytecode files from the index so they are not
    # re-staged by the subsequent ``git add -A``.
    untrack_cmd = (
        f"cd {workdir} && "
        "git rm -r --cached __pycache__ '*.pyc' '*.pyo' '*.pyd' 2>/dev/null || true"
    )
    await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(command=untrack_cmd, timeout_seconds=30),
    )

    logger.info("gitignore_bytecode_sanitized workdir=%s added=%s", workdir, missing_entries)


class GitOperations:
    """Encapsulates git operations executed inside a sandbox."""

    def __init__(self, sandbox_manager: SandboxManager, sandbox_id: str) -> None:
        self._sandbox_manager = sandbox_manager
        self._sandbox_id = sandbox_id

    async def rebase_on_upstream(
        self,
        base_branch: str,
        workdir: str,
    ) -> dict[str, Any]:
        """Attempt to rebase the current branch on *base_branch*.

        Returns a status dict with keys ``success`` (bool) and ``message`` (str).

        .. note::
           This performs a **local** rebase only (no ``git fetch``).  A fetch
           would require network access which may be disabled in the sandbox.
           TODO: fetch from origin once ``reconnect_network`` is available on
           ``SandboxManager``.
        """
        from lintel.sandbox.types import SandboxJob

        result = await self._sandbox_manager.execute(
            self._sandbox_id,
            SandboxJob(
                command=f"cd {workdir} && git rebase {base_branch}",
                timeout_seconds=60,
            ),
        )

        if result.exit_code != 0:
            # Abort the failed rebase so the tree is left clean
            await self._sandbox_manager.execute(
                self._sandbox_id,
                SandboxJob(
                    command=f"cd {workdir} && git rebase --abort",
                    timeout_seconds=30,
                ),
            )
            logger.warning(
                "rebase_conflict base_branch=%s stdout=%s",
                base_branch,
                result.stdout[:200] if result.stdout else "",
            )
            return {
                "success": False,
                "message": (
                    f"Rebase on {base_branch} failed — conflicts detected. "
                    "Manual resolution may be needed."
                ),
            }

        return {"success": True, "message": f"Rebased successfully on {base_branch}."}


# Backward-compatible wrapper
async def rebase_on_upstream(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    base_branch: str,
    workdir: str,
) -> dict[str, Any]:
    """Attempt to rebase the current branch on *base_branch*.

    Backward-compatible wrapper around :class:`GitOperations`.
    """
    ops = GitOperations(sandbox_manager, sandbox_id)
    return await ops.rebase_on_upstream(base_branch, workdir)
