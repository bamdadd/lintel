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

        try:
            await asyncio.to_thread(client.images.get, config.image)
        except Exception:
            await asyncio.to_thread(client.images.pull, config.image)

        create_kwargs: dict[str, Any] = {
            "image": config.image,
            "command": "sleep infinity",
            "detach": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "read_only": False,
            "network_mode": "bridge" if config.network_enabled else "none",
            "mem_limit": config.memory_limit,
            "nano_cpus": config.cpu_quota * 10000,
            "cpuset_cpus": f"0-{max(0, config.cpu_quota // 100000 - 1)}",
            "pids_limit": 256,
            "tmpfs": {"/tmp": "size=200m,exec", "/workspace": "size=4g,exec"},
            "environment": environment,
            "labels": {
                "lintel.sandbox_id": sandbox_id,
                "lintel.thread_ref": thread_ref.stream_id,
            },
        }

        # Ensure DNS works in bridge mode (Docker Desktop may not propagate host DNS)
        if config.network_enabled:
            create_kwargs["dns"] = ["8.8.8.8", "8.8.4.4"]

        container = await asyncio.to_thread(
            client.containers.create,
            **create_kwargs,
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
                cmd=["/bin/sh", "-c", job.command],
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
        # Use cat via execute — more reliable than get_archive on mounted volumes
        from lintel.contracts.types import SandboxJob

        result = await self.execute(
            sandbox_id,
            SandboxJob(command=f"cat {path}", timeout_seconds=10),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to read {path}: {result.stderr}")
        return result.stdout

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        import base64

        from lintel.contracts.types import SandboxJob

        dest_dir = os.path.dirname(path) or "/"
        await self.execute(
            sandbox_id,
            SandboxJob(command=f"mkdir -p {dest_dir}", timeout_seconds=10),
        )
        # Use base64 to safely transfer content (avoids shell escaping issues)
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=f"echo '{encoded}' | base64 -d > {path}",
                timeout_seconds=30,
            ),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to write {path}: {result.stderr}")

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

    async def get_logs(self, sandbox_id: str, tail: int = 200) -> str:
        container = self._get_container(sandbox_id)
        raw: bytes = await asyncio.to_thread(
            container.logs,
            stdout=True,
            stderr=True,
            tail=tail,
        )
        return raw.decode("utf-8", errors="replace")

    async def collect_artifacts(
        self, sandbox_id: str, workdir: str = "/workspace"
    ) -> dict[str, Any]:
        from lintel.contracts.types import SandboxJob

        # Try to find git repos under the workdir
        find_result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=f"find {workdir} -name .git -type d -maxdepth 3 2>/dev/null | head -1",
                timeout_seconds=10,
            ),
        )
        git_dir = find_result.stdout.strip()
        repo_dir = git_dir.rsplit("/.git", 1)[0] if git_dir else workdir

        # Stage all changes (including new untracked files) so they appear
        # in the diff.  `git add -N` marks new files as "intent to add"
        # without staging content, but `git add -A` followed by
        # `git diff --cached` is more reliable for capturing everything.
        await self.execute(
            sandbox_id,
            SandboxJob(command="git add -A", workdir=repo_dir, timeout_seconds=10),
        )

        # Exclude noisy lock files from the diff
        exclude = "':!*.lock' ':!package-lock.json' ':!uv.lock' ':!bun.lock'"

        # Show all changes vs the base branch (committed + staged).
        # After git add -A above, all changes are staged, so we diff
        # against origin/main to capture everything in one shot.
        result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "git diff --cached origin/main"
                    f" -- . {exclude} 2>/dev/null"
                    " || git diff --cached main"
                    f" -- . {exclude} 2>/dev/null"
                    f" || git diff --cached -- . {exclude}"
                ),
                workdir=repo_dir,
            ),
        )
        return {"type": "diff", "content": result.stdout, "exit_code": result.exit_code}

    async def reconnect_network(self, sandbox_id: str) -> None:
        """Reconnect the sandbox container to the bridge network."""
        container = self._get_container(sandbox_id)
        client = self._get_client()
        await asyncio.to_thread(container.reload)
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        if "bridge" not in networks:
            bridge = await asyncio.to_thread(client.networks.get, "bridge")
            await asyncio.to_thread(bridge.connect, container)

    async def disconnect_network(self, sandbox_id: str) -> None:
        """Disconnect the sandbox container from all networks."""
        container = self._get_container(sandbox_id)
        client = self._get_client()
        await asyncio.to_thread(container.reload)
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for net_name in networks:
            if net_name == "none":
                continue
            network = await asyncio.to_thread(client.networks.get, net_name)
            await asyncio.to_thread(network.disconnect, container)

    async def destroy(self, sandbox_id: str) -> None:
        container = self._containers.pop(sandbox_id, None)
        if container is None:
            # Only attempt a Docker label lookup if a client is already
            # initialised — avoids connecting to Docker (and failing) when
            # the sandbox_id is simply unknown (e.g. in tests or after a
            # clean restart where no containers were ever created).
            if self._client is not None:
                matches = await asyncio.to_thread(
                    self._client.containers.list,
                    filters={"label": f"lintel.sandbox_id={sandbox_id}"},
                    all=True,
                )
                if matches:
                    container = matches[0]
        if container:
            await asyncio.to_thread(container.remove, force=True)

    async def recover_containers(self) -> list[str]:
        """Re-attach to containers from previous runs using Docker labels."""
        client = self._get_client()
        containers = await asyncio.to_thread(
            client.containers.list,
            filters={"label": "lintel.sandbox_id"},
            all=True,
        )
        recovered: list[str] = []
        for container in containers:
            sandbox_id = container.labels.get("lintel.sandbox_id", "")
            if sandbox_id and sandbox_id not in self._containers:
                status: str = container.status
                if status in ("running", "paused", "restarting", "created"):
                    self._containers[sandbox_id] = container
                    recovered.append(sandbox_id)
                else:
                    # Dead/exited containers — clean up
                    await asyncio.to_thread(container.remove, force=True)
        return recovered
