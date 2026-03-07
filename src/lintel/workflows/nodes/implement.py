"""Implementation workflow node — creates sandbox and runs agent tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager
    from lintel.contracts.types import SandboxConfig
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)


async def spawn_implementation(
    state: ThreadWorkflowState,
    *,
    sandbox_manager: SandboxManager,
    sandbox_config: SandboxConfig | None = None,
) -> dict[str, Any]:
    """Create a sandbox, execute implementation, and collect artifacts."""
    from lintel.contracts.types import SandboxConfig, ThreadRef

    if sandbox_config is None:
        sandbox_config = SandboxConfig()

    thread_ref_str = state["thread_ref"]
    parts = thread_ref_str.replace("thread:", "").split(":")
    thread_ref = ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )

    sandbox_id = await sandbox_manager.create(sandbox_config, thread_ref)
    try:
        # TODO: Wire agent tool loop here (ToolNode with sandbox tools)
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id)
        return {
            "sandbox_id": None,
            "sandbox_results": [artifacts],
        }
    finally:
        await sandbox_manager.destroy(sandbox_id)
