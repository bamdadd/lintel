"""Protocol interfaces for sandbox management.

Domain code depends on these abstractions. Infrastructure provides implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus


class SandboxManager(Protocol):
    """Manages isolated sandbox environments for agent code execution."""

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str: ...

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult: ...

    async def execute_stream(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> AsyncIterator[str]:
        """Execute a command and yield stdout/stderr lines as they arrive.

        Returns an async iterator of output lines (combined stdout+stderr).
        The final yielded item is a sentinel ``__EXIT:<code>__`` carrying the
        exit code so callers can detect success/failure without a separate call.
        """
        yield ""  # pragma: no cover

    async def read_file(
        self,
        sandbox_id: str,
        path: str,
    ) -> str: ...

    async def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str,
    ) -> None: ...

    async def list_files(
        self,
        sandbox_id: str,
        path: str = "/workspace",
    ) -> list[str]: ...

    async def get_status(
        self,
        sandbox_id: str,
    ) -> SandboxStatus: ...

    async def get_logs(
        self,
        sandbox_id: str,
        tail: int = 200,
    ) -> str: ...

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, Any]: ...

    async def reconnect_network(
        self,
        sandbox_id: str,
    ) -> None: ...

    async def disconnect_network(
        self,
        sandbox_id: str,
    ) -> None: ...

    async def destroy(
        self,
        sandbox_id: str,
    ) -> None: ...
