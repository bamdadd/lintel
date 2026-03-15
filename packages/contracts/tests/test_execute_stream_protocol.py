"""Tests for execute_stream method on the SandboxManager protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.sandbox.protocols import SandboxManager

from lintel.contracts.types import ThreadRef  # noqa: TC001
from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus


class TestExecuteStreamProtocolConformance:
    async def test_fake_satisfies_protocol(self) -> None:
        """A class implementing all SandboxManager methods including execute_stream
        can be used as a SandboxManager."""

        class FakeSandboxWithStream:
            async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
                return "sandbox-1"

            async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
                return SandboxResult(exit_code=0)

            async def execute_stream(self, sandbox_id: str, job: SandboxJob) -> AsyncIterator[str]:
                return self._stream()

            async def _stream(self) -> AsyncIterator[str]:
                yield "hello"
                yield "__EXIT:0__"

            async def read_file(self, sandbox_id: str, path: str) -> str:
                return ""

            async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
                pass

            async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
                return []

            async def get_status(self, sandbox_id: str) -> SandboxStatus:
                return SandboxStatus.RUNNING

            async def get_logs(self, sandbox_id: str, tail: int = 200) -> str:
                return ""

            async def collect_artifacts(
                self, sandbox_id: str, workdir: str = "/workspace"
            ) -> dict[str, Any]:
                return {}

            async def reconnect_network(self, sandbox_id: str) -> None:
                pass

            async def disconnect_network(self, sandbox_id: str) -> None:
                pass

            async def destroy(self, sandbox_id: str) -> None:
                pass

        # Structural typing: assignment verifies protocol conformance at type-check time.
        sandbox: SandboxManager = FakeSandboxWithStream()  # type: ignore[assignment]
        assert sandbox is not None

    async def test_execute_stream_yields_lines(self) -> None:
        """execute_stream yields output lines followed by sentinel."""

        class FakeSandboxWithStream:
            async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
                return "sandbox-1"

            async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
                return SandboxResult(exit_code=0)

            async def execute_stream(self, sandbox_id: str, job: SandboxJob) -> AsyncIterator[str]:
                return self._stream()

            async def _stream(self) -> AsyncIterator[str]:
                for line in ["line one", "line two"]:
                    yield line
                yield "__EXIT:0__"

            async def read_file(self, sandbox_id: str, path: str) -> str:
                return ""

            async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
                pass

            async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
                return []

            async def get_status(self, sandbox_id: str) -> SandboxStatus:
                return SandboxStatus.RUNNING

            async def get_logs(self, sandbox_id: str, tail: int = 200) -> str:
                return ""

            async def collect_artifacts(
                self, sandbox_id: str, workdir: str = "/workspace"
            ) -> dict[str, Any]:
                return {}

            async def reconnect_network(self, sandbox_id: str) -> None:
                pass

            async def disconnect_network(self, sandbox_id: str) -> None:
                pass

            async def destroy(self, sandbox_id: str) -> None:
                pass

        fake = FakeSandboxWithStream()
        job = SandboxJob(command="echo hello")
        lines = []
        async for line in await fake.execute_stream("sandbox-1", job):
            lines.append(line)

        assert lines == ["line one", "line two", "__EXIT:0__"]
