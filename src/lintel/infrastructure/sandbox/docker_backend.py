"""Docker-based sandbox backend with defense-in-depth security."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.contracts.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
)

from ._tar_helpers import create_tar, extract_file

if TYPE_CHECKING:
    from lintel.contracts.types import (
        SandboxConfig,
        SandboxJob,
        SandboxResult,
        SandboxStatus,
        ThreadRef,
    )


class DockerSandboxManager:
    """Implements SandboxManager protocol using Docker containers."""

    def __init__(self) -> None:
        self._containers: dict[str, Any] = {}
        self._client: Any | None = None

    def _get_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            import docker  # type: ignore[import-untyped]

            self._client = docker.from_env()
        return self._client

    def _get_container(self, sandbox_id: str) -> Any:  # noqa: ANN401
        container = self._containers.get(sandbox_id)
        if container is None:
            raise SandboxNotFoundError(sandbox_id)
        return container

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str:
        sandbox_id = str(uuid4())
        client = self._get_client()

        environment = dict(config.environment) if config.environment else {}

        container = await asyncio.to_thread(
            client.containers.create,
            image=config.image,
            command="sleep infinity",
            detach=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            read_only=False,
            network_mode="bridge" if config.network_enabled else "none",
            mem_limit=config.memory_limit,
            cpu_period=100000,
            cpu_quota=config.cpu_quota,
            pids_limit=256,
            user="1000:1000",
            tmpfs={"/tmp": "size=100m,noexec"},
            environment=environment,
            labels={
                "lintel.sandbox_id": sandbox_id,
                "lintel.thread_ref": thread_ref.stream_id,
            },
        )
        await asyncio.to_thread(container.start)
        self._containers[sandbox_id] = container
        return sandbox_id

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult:
        from lintel.contracts.types import SandboxResult

        container = self._get_container(sandbox_id)

        async def _run() -> SandboxResult:
            exec_result = await asyncio.to_thread(
                container.exec_run,
                cmd=job.command,
                workdir=job.workdir or "/workspace",
                demux=True,
            )
            stdout_bytes, stderr_bytes = exec_result.output
            return SandboxResult(
                exit_code=exec_result.exit_code,
                stdout=(stdout_bytes or b"").decode("utf-8", errors="replace"),
                stderr=(stderr_bytes or b"").decode("utf-8", errors="replace"),
            )

        try:
            return await asyncio.wait_for(_run(), timeout=job.timeout_seconds)
        except TimeoutError as exc:
            raise SandboxTimeoutError(
                f"Command timed out after {job.timeout_seconds}s: {job.command}"
            ) from exc

    async def read_file(self, sandbox_id: str, path: str) -> str:
        container = self._get_container(sandbox_id)
        try:
            bits, _stat = await asyncio.to_thread(container.get_archive, path)
            return extract_file(bits)
        except SandboxNotFoundError:
            raise
        except Exception as exc:
            raise SandboxExecutionError(f"Failed to read {path}") from exc

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        container = self._get_container(sandbox_id)
        tar_stream = create_tar(path, content)
        dest_dir = os.path.dirname(path) or "/workspace"
        try:
            await asyncio.to_thread(container.put_archive, dest_dir, tar_stream)
        except SandboxNotFoundError:
            raise
        except Exception as exc:
            raise SandboxExecutionError(f"Failed to write {path}") from exc

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        from lintel.contracts.types import SandboxJob

        result = await self.execute(
            sandbox_id, SandboxJob(command=f"ls -1 {path}", timeout_seconds=10)
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to list {path}: {result.stderr}")
        return [f for f in result.stdout.strip().split("\n") if f]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        from lintel.contracts.types import SandboxStatus

        container = self._get_container(sandbox_id)
        await asyncio.to_thread(container.reload)
        state: str = container.status
        status_map: dict[str, SandboxStatus] = {
            "created": SandboxStatus.CREATING,
            "running": SandboxStatus.RUNNING,
            "paused": SandboxStatus.RUNNING,
            "restarting": SandboxStatus.RUNNING,
            "removing": SandboxStatus.DESTROYED,
            "exited": SandboxStatus.COMPLETED,
            "dead": SandboxStatus.FAILED,
        }
        return status_map.get(state, SandboxStatus.FAILED)

    async def collect_artifacts(self, sandbox_id: str) -> dict[str, Any]:
        from lintel.contracts.types import SandboxJob

        result = await self.execute(
            sandbox_id, SandboxJob(command="git diff", workdir="/workspace")
        )
        return {"type": "diff", "content": result.stdout, "exit_code": result.exit_code}

    async def destroy(self, sandbox_id: str) -> None:
        container = self._containers.pop(sandbox_id, None)
        if container:
            await asyncio.to_thread(container.remove, force=True)

    async def recover_orphans(self) -> list[str]:
        """Discover and destroy orphaned containers from previous runs."""
        client = self._get_client()
        containers = await asyncio.to_thread(
            client.containers.list,
            filters={"label": "lintel.sandbox_id"},
            all=True,
        )
        destroyed: list[str] = []
        for container in containers:
            sandbox_id = container.labels.get("lintel.sandbox_id", "")
            if sandbox_id and sandbox_id not in self._containers:
                await asyncio.to_thread(container.remove, force=True)
                destroyed.append(sandbox_id)
        return destroyed
