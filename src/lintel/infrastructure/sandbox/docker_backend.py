"""Docker-based sandbox backend with defense-in-depth security."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from lintel.contracts.types import SandboxConfig, SandboxJob, SandboxResult, ThreadRef


class DockerSandboxManager:
    """Implements SandboxManager protocol using Docker containers."""

    def __init__(self) -> None:
        self._containers: dict[str, Any] = {}

    def _get_client(self) -> object:
        import docker  # type: ignore[import-untyped]

        return docker.from_env()

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str:
        sandbox_id = str(uuid4())
        client: Any = self._get_client()

        container = await asyncio.to_thread(
            client.containers.create,
            image=config.image,
            command="sleep infinity",
            detach=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            read_only=True,
            network_mode="none",
            mem_limit=config.memory_limit,
            cpu_period=100000,
            cpu_quota=config.cpu_quota,
            user="1000:1000",
            tmpfs={"/tmp": "size=100m,noexec"},
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

        container = self._containers[sandbox_id]
        exec_result = await asyncio.to_thread(
            container.exec_run,
            cmd=job.command,
            workdir=job.workdir or "/workspace",
        )
        return SandboxResult(
            exit_code=exec_result.exit_code,
            stdout=exec_result.output.decode("utf-8", errors="replace"),
        )

    async def collect_artifacts(self, sandbox_id: str) -> list[dict[str, Any]]:
        container = self._containers[sandbox_id]
        result = await asyncio.to_thread(
            container.exec_run,
            cmd="git diff",
            workdir="/workspace",
        )
        return [{"type": "diff", "content": result.output.decode()}]

    async def destroy(self, sandbox_id: str) -> None:
        container = self._containers.pop(sandbox_id, None)
        if container:
            await asyncio.to_thread(container.remove, force=True)
