"""Sandbox manager protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.contracts.types import SandboxConfig, SandboxJob, SandboxResult, ThreadRef


class SandboxManager(Protocol):
    """Manages isolated sandbox containers for code execution."""

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str:
        """Create sandbox, return sandbox_id."""
        ...

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult: ...

    async def collect_artifacts(self, sandbox_id: str) -> list[dict[str, Any]]: ...

    async def destroy(self, sandbox_id: str) -> None: ...
