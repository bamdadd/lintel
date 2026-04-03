"""Test configuration for lintel-sandboxes-api."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from lintel.contracts.types import ThreadRef  # noqa: TC001
from lintel.sandbox.errors import SandboxNotFoundError
from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus


class DummySandboxManager:
    """In-memory sandbox manager for API tests."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        self.last_config = config
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        if job.command.startswith("cat "):
            path = job.command[4:].strip()
            content = self._sandboxes[sandbox_id].get(path, "")
            if not content:
                return SandboxResult(exit_code=1, stdout="", stderr=f"cat: {path}: No such file")
            return SandboxResult(exit_code=0, stdout=content)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return self._sandboxes[sandbox_id].get(path, "")

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        self._sandboxes[sandbox_id][path] = content

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return [k for k in self._sandboxes[sandbox_id] if k.startswith(path)]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxStatus.RUNNING

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, Any]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return {"type": "diff", "content": ""}

    async def destroy(self, sandbox_id: str) -> None:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        del self._sandboxes[sandbox_id]


@pytest.fixture()
def dummy_sandbox_manager() -> DummySandboxManager:
    return DummySandboxManager()


@pytest.fixture()
def sandbox_manager_factory() -> type[DummySandboxManager]:
    """Return the DummySandboxManager class for tests that need multiple instances."""
    return DummySandboxManager
