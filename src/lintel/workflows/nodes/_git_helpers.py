"""Shared git helper utilities for workflow nodes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager

from lintel.contracts.workflow_models import RebaseResult

logger = logging.getLogger(__name__)


async def rebase_on_upstream(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    base_branch: str,
    workdir: str = "/workspace/repo",
) -> RebaseResult:
    """Attempt to rebase the current branch on *base_branch*.

    Returns a :class:`RebaseResult` with ``success`` and ``message`` fields.

    .. note::
       This performs a **local** rebase only (no ``git fetch``).  A fetch
       would require network access which may be disabled in the sandbox.
       TODO: fetch from origin once ``reconnect_network`` is available on
       ``SandboxManager``.
    """
    from lintel.contracts.types import SandboxJob

    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"cd {workdir} && git rebase {base_branch}",
            timeout_seconds=60,
        ),
    )

    if result.exit_code != 0:
        # Abort the failed rebase so the tree is left clean
        await sandbox_manager.execute(
            sandbox_id,
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
        return RebaseResult(
            success=False,
            message=(
                f"Rebase on {base_branch} failed — conflicts detected. "
                "Manual resolution may be needed."
            ),
        )

    return RebaseResult(success=True, message=f"Rebased successfully on {base_branch}.")
