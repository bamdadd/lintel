"""Docker-based sandbox backend with defense-in-depth security."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.sandbox.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
    StorageLimitExceededError,
)
from lintel.sandbox.resource_guard import (
    ResourceGuard,
    build_egress_iptables_script,
    build_network_policy_script,
    build_security_opt,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.types import (
        PreviewDetection,
        PreviewInfo,
        SandboxConfig,
        SandboxJob,
        SandboxResult,
        SandboxStatus,
        StorageUsage,
    )


class DockerSandboxManager:
    """Implements SandboxManager protocol using Docker containers."""

    def __init__(self, max_sandboxes: int = 8) -> None:
        self._containers: dict[str, Any] = {}
        self._client: Any | None = None
        self._max_sandboxes = max_sandboxes
        self._active = 0
        self._lock = asyncio.Lock()
        self._guards: dict[str, ResourceGuard] = {}
        self._configs: dict[str, SandboxConfig] = {}
        self._networks: dict[str, str] = {}  # sandbox_id → Docker network name
        self._previews: dict[str, PreviewInfo] = {}  # sandbox_id → active preview

    def _get_client(self) -> Any:  # noqa: ANN401
        if self._client is None:
            import docker  # type: ignore[import-untyped]

            self._client = docker.from_env()
        return self._client

    def _get_container(self, sandbox_id: str) -> Any:  # noqa: ANN401
        container = self._containers.get(sandbox_id)
        if container is None:
            # Recovery: look up by label in Docker (survives server restarts)
            container = self._recover_container(sandbox_id)
        if container is None:
            raise SandboxNotFoundError(sandbox_id)
        return container

    def _recover_container(self, sandbox_id: str) -> Any | None:  # noqa: ANN401
        """Try to find a running container by its lintel.sandbox_id label."""
        import structlog

        log = structlog.get_logger()
        client = self._get_client()
        containers = client.containers.list(
            all=True,
            filters={"label": f"lintel.sandbox_id={sandbox_id}"},
        )
        if containers:
            container = containers[0]
            self._containers[sandbox_id] = container
            log.info(
                "sandbox_recovered_from_docker",
                sandbox_id=sandbox_id[:12],
                container_id=container.short_id,
            )
            return container
        log.warning("sandbox_recovery_failed", sandbox_id=sandbox_id[:12])
        return None

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

        # Determine network mode: per-sandbox isolated network, bridge, or none
        net_policy = config.network_policy
        sandbox_network_name: str | None = None
        if config.network_enabled and net_policy is not None and net_policy.isolate:
            sandbox_network_name = f"lintel-sandbox-{sandbox_id[:12]}"
            await asyncio.to_thread(
                client.networks.create,
                sandbox_network_name,
                driver="bridge",
                internal=False,
                labels={"lintel.sandbox_id": sandbox_id},
            )
            network_mode = sandbox_network_name
        elif config.network_enabled:
            network_mode = "bridge"
        else:
            network_mode = "none"

        create_kwargs: dict[str, Any] = {
            "image": config.image,
            "command": "sleep infinity",
            "detach": True,
            "cap_drop": ["ALL"],
            "security_opt": build_security_opt(config.resource_limits),
            "read_only": False,
            "network_mode": network_mode,
            "mem_limit": config.memory_limit,
            "nano_cpus": config.cpu_quota * 10000,
            "cpuset_cpus": f"0-{max(0, config.cpu_quota // 100000 - 1)}",
            "pids_limit": min(config.resource_limits.max_processes, 512),
            "storage_opt": {"size": f"{config.resource_limits.max_disk_mb}m"},
            "tmpfs": {
                "/tmp": "size=200m,exec,uid=1000,gid=1000",
            },
            "user": "vscode",
            "environment": environment,
            "labels": {
                "lintel.sandbox_id": sandbox_id,
                "lintel.thread_ref": thread_ref.stream_id,
                "lintel.image": config.image,
                "lintel.network_enabled": str(config.network_enabled),
                "lintel.workspace_id": thread_ref.workspace_id,
                "lintel.channel_id": thread_ref.channel_id,
            },
        }

        # Workspace volume (disk-backed, not tmpfs)
        import docker as docker_lib

        workspace_vol = f"lintel-workspace-{sandbox_id}"
        create_kwargs.setdefault("mounts", []).append(
            docker_lib.types.Mount(
                target="/workspace",
                source=workspace_vol,
                type="volume",
                read_only=False,
            )
        )

        # Bind mounts (e.g. ~/.claude for Claude Code credentials)
        if config.mounts:
            create_kwargs["mounts"].extend(
                docker_lib.types.Mount(
                    target=target,
                    source=source,
                    type=mount_type,
                    read_only=True,
                )
                for source, target, mount_type in config.mounts
            )
            # cap_drop=ALL removes DAC_READ_SEARCH, which blocks reading bind mounts
            create_kwargs["cap_add"] = ["DAC_READ_SEARCH"]

        # Ensure DNS works in bridge mode (Docker Desktop may not propagate host DNS)
        if config.network_enabled:
            create_kwargs["dns"] = ["8.8.8.8", "8.8.4.4"]

        container = await asyncio.to_thread(
            client.containers.create,
            **create_kwargs,
        )
        try:
            await asyncio.to_thread(container.start)
            # Fix ownership on the Docker volume (created as root, container runs as vscode)
            chown_cmd = "chown -R vscode:vscode /workspace"
            await asyncio.to_thread(container.exec_run, chown_cmd, user="root")
        except Exception:
            # Clean up the container and volume on failure to avoid zombies
            import contextlib

            with contextlib.suppress(Exception):
                await asyncio.to_thread(container.remove, force=True)
            with contextlib.suppress(Exception):
                vol = await asyncio.to_thread(client.volumes.get, f"lintel-workspace-{sandbox_id}")
                await asyncio.to_thread(vol.remove, force=True)
            raise
        self._containers[sandbox_id] = container
        self._configs[sandbox_id] = config
        self._guards[sandbox_id] = ResourceGuard(config.tool_limits)
        if sandbox_network_name is not None:
            self._networks[sandbox_id] = sandbox_network_name

        # Apply network restrictions if configured
        if config.network_enabled:
            # New NetworkPolicy takes precedence over legacy NetworkEgressPolicy
            if net_policy is not None and net_policy.allowed_endpoints:
                policy_script = build_network_policy_script(net_policy)
                if policy_script:
                    await asyncio.to_thread(
                        container.exec_run,
                        ["/bin/sh", "-c", policy_script],
                        user="root",
                    )
            elif config.network_egress.allowed_domains:
                egress_script = build_egress_iptables_script(config.network_egress)
                if egress_script:
                    await asyncio.to_thread(
                        container.exec_run,
                        ["/bin/sh", "-c", egress_script],
                        user="root",
                    )

        return sandbox_id

    def get_guard(self, sandbox_id: str) -> ResourceGuard | None:
        """Return the resource guard for a sandbox, if it exists."""
        return self._guards.get(sandbox_id)

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult:
        from lintel.sandbox.types import SandboxResult

        guard = self._guards.get(sandbox_id)
        if guard is not None:
            guard.record_tool_call()

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
        except Exception as exc:
            err_msg = str(exc)
            if "is not running" in err_msg or "is restarting" in err_msg:
                raise SandboxExecutionError(
                    f"Sandbox {sandbox_id[:12]} is not running: {err_msg}"
                ) from exc
            raise

    async def execute_stream(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> AsyncIterator[str]:
        """Execute a command and yield stdout/stderr lines as they arrive.

        Streams output using the Docker low-level API exec_create/exec_start.
        Yields complete lines (stripping empty ones). The final item is a
        sentinel ``__EXIT:<code>__`` so callers can detect success/failure.

        Raises SandboxTimeoutError if a chunk read exceeds job.timeout_seconds.
        """
        container = self._get_container(sandbox_id)
        api = container.client.api

        exec_id = await asyncio.to_thread(
            api.exec_create,
            container.id,
            ["/bin/sh", "-c", job.command],
            workdir=job.workdir or "/workspace",
        )
        output_gen = await asyncio.to_thread(
            api.exec_start,
            exec_id,
            stream=True,
            demux=True,
        )

        async def _stream() -> AsyncIterator[str]:
            stdout_buf = ""
            stderr_buf = ""

            def _next_chunk() -> tuple[bytes | None, bytes | None] | None:
                try:
                    return next(output_gen)  # type: ignore[no-any-return]
                except StopIteration:
                    return None

            while True:
                try:
                    chunk = await asyncio.wait_for(
                        asyncio.to_thread(_next_chunk),
                        timeout=job.timeout_seconds,
                    )
                except TimeoutError as exc:
                    raise SandboxTimeoutError(
                        f"Command timed out after {job.timeout_seconds}s: {job.command}"
                    ) from exc

                if chunk is None:
                    break

                stdout_bytes, stderr_bytes = chunk

                if stdout_bytes:
                    stdout_buf += stdout_bytes.decode("utf-8", errors="replace")
                if stderr_bytes:
                    stderr_buf += stderr_bytes.decode("utf-8", errors="replace")

                # Yield complete lines from stdout buffer
                while "\n" in stdout_buf:
                    line, stdout_buf = stdout_buf.split("\n", 1)
                    if line.strip():
                        yield line

                # Yield complete lines from stderr buffer
                while "\n" in stderr_buf:
                    line, stderr_buf = stderr_buf.split("\n", 1)
                    if line.strip():
                        yield line

            # Flush remaining buffers
            if stdout_buf.strip():
                yield stdout_buf
            if stderr_buf.strip():
                yield stderr_buf

            # Emit exit code sentinel
            inspect = await asyncio.to_thread(api.exec_inspect, exec_id)
            exit_code = inspect.get("ExitCode", -1)
            yield f"__EXIT:{exit_code}__"

        return _stream()

    async def read_file(self, sandbox_id: str, path: str) -> str:
        # Use cat via execute — more reliable than get_archive on mounted volumes
        from lintel.sandbox.types import SandboxJob

        result = await self.execute(
            sandbox_id,
            SandboxJob(command=f"cat {path}", timeout_seconds=10),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to read {path}: {result.stderr}")
        return result.stdout

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        guard = self._guards.get(sandbox_id)
        if guard is not None:
            guard.record_file_write()

        import io
        import tarfile

        from lintel.sandbox.types import SandboxJob

        dest_dir = os.path.dirname(path) or "/"
        await self.execute(
            sandbox_id,
            SandboxJob(command=f"mkdir -p {dest_dir}", timeout_seconds=10),
        )

        # Use Docker put_archive API to write files of any size (avoids ARG_MAX
        # shell limits that break exec-based writes for files > ~100KB).
        container = self._get_container(sandbox_id)
        file_bytes = content.encode("utf-8")
        filename = os.path.basename(path)

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(file_bytes)
            info.uid = 1000
            info.gid = 1000
            tar.addfile(info, io.BytesIO(file_bytes))
        buf.seek(0)

        await asyncio.to_thread(container.put_archive, dest_dir, buf)

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        from lintel.sandbox.types import SandboxJob

        result = await self.execute(
            sandbox_id, SandboxJob(command=f"ls -1 {path}", timeout_seconds=10)
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to list {path}: {result.stderr}")
        return [f for f in result.stdout.strip().split("\n") if f]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        from lintel.sandbox.types import SandboxStatus

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

    async def get_storage_usage(self, sandbox_id: str) -> StorageUsage:
        """Return current workspace storage usage for a sandbox.

        Runs ``du -sb /workspace`` inside the container and parses the result.
        """
        from lintel.sandbox.types import SandboxJob, StorageUsage

        result = await self.execute(
            sandbox_id,
            SandboxJob(command="du -sb /workspace", timeout_seconds=30),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(
                f"Failed to check storage for {sandbox_id[:12]}: {result.stderr}"
            )
        # du -sb output: "<bytes>\t/workspace"
        used_bytes = int(result.stdout.strip().split("\t")[0])
        config = self._configs.get(sandbox_id)
        limit_gb = config.storage_limits.max_storage_gb if config else 4
        limit_bytes = limit_gb * 1024 * 1024 * 1024
        return StorageUsage(used_bytes=used_bytes, limit_bytes=limit_bytes)

    async def cleanup_workspace(
        self,
        sandbox_id: str,
        *,
        paths: tuple[str, ...] = (
            "/workspace/.git/objects/pack/*.old",
            "/workspace/**/__pycache__",
            "/workspace/**/*.pyc",
            "/workspace/**/node_modules/.cache",
            "/workspace/**/.pytest_cache",
            "/workspace/**/.mypy_cache",
        ),
    ) -> int:
        """Remove common ephemeral files from the workspace to reclaim space.

        Returns the number of bytes freed (approximate, via du before/after).
        """
        usage_before = await self.get_storage_usage(sandbox_id)

        from lintel.sandbox.types import SandboxJob

        # Build a single rm command for all cleanup paths
        rm_parts = [f"rm -rf {p}" for p in paths]
        cleanup_cmd = " && ".join(rm_parts)
        await self.execute(
            sandbox_id,
            SandboxJob(command=cleanup_cmd, timeout_seconds=60),
        )

        usage_after = await self.get_storage_usage(sandbox_id)
        return max(0, usage_before.used_bytes - usage_after.used_bytes)

    async def check_storage_limit(self, sandbox_id: str) -> StorageUsage:
        """Check storage and raise if the hard limit is exceeded.

        If usage exceeds the cleanup threshold (default 80%), runs automatic
        cleanup first. If still over the hard limit after cleanup, raises
        ``StorageLimitExceededError``.
        """
        usage = await self.get_storage_usage(sandbox_id)
        config = self._configs.get(sandbox_id)
        threshold_pct = config.storage_limits.cleanup_threshold_pct if config else 80

        if usage.used_pct >= threshold_pct:
            await self.cleanup_workspace(sandbox_id)
            usage = await self.get_storage_usage(sandbox_id)

        if usage.used_pct >= 100.0:
            raise StorageLimitExceededError(
                used_mb=usage.used_mb,
                limit_mb=usage.limit_bytes // (1024 * 1024),
            )
        return usage

    async def collect_artifacts(
        self, sandbox_id: str, workdir: str = "/workspace"
    ) -> dict[str, Any]:
        from lintel.sandbox.types import SandboxJob

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

    async def _detect_preview(self, sandbox_id: str) -> PreviewDetection:
        """Detect a runnable app inside the sandbox workspace."""
        from lintel.sandbox.types import PreviewDetection, SandboxJob

        # Check for package.json start script
        result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "cat /workspace/package.json 2>/dev/null"
                    " | python3 -c 'import sys,json;"
                    "d=json.load(sys.stdin);"
                    's=d.get("scripts",{});'
                    'print(s.get("dev","") or s.get("start",""))\''
                    " 2>/dev/null || echo ''"
                ),
                timeout_seconds=10,
            ),
        )
        if result.exit_code == 0 and result.stdout.strip():
            script = result.stdout.strip()
            # Detect common ports from scripts
            port = 3000
            if "vite" in script or "next" in script or "react-scripts" in script:
                port = 3000
            elif ":8080" in script:
                port = 8080
            elif ":5173" in script:
                port = 5173
            framework = "node"
            if "next" in script:
                framework = "nextjs"
            elif "vite" in script:
                framework = "vite"
            elif "react-scripts" in script:
                framework = "react"
            return PreviewDetection(
                detected=True,
                command="npm run dev" if "dev" in script else "npm start",
                port=port,
                framework=framework,
            )

        # Check for Python web frameworks (uvicorn, flask, etc.)
        result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "grep -rl 'uvicorn\\|flask\\|FastAPI\\|Django' "
                    "/workspace/*.py /workspace/**/*.py 2>/dev/null | head -1"
                ),
                timeout_seconds=10,
            ),
        )
        if result.exit_code == 0 and result.stdout.strip():
            return PreviewDetection(
                detected=True,
                command="python -m uvicorn main:app --host 0.0.0.0 --port 8000",
                port=8000,
                framework="python",
            )

        return PreviewDetection(detected=False)

    async def start_preview(
        self,
        sandbox_id: str,
        *,
        command: str = "",
        port: int = 0,
    ) -> PreviewInfo:
        """Start a preview server inside the sandbox and expose the port.

        If no command/port is given, auto-detect the app framework.
        Returns a PreviewInfo with the host-accessible URL.
        """
        from datetime import UTC, datetime

        from lintel.sandbox.types import PreviewInfo, PreviewStatus, SandboxJob

        # If already running, return existing info
        existing = self._previews.get(sandbox_id)
        if existing is not None and existing.status == PreviewStatus.RUNNING:
            return existing

        # Auto-detect if not specified
        if not command or port == 0:
            detection = await self._detect_preview(sandbox_id)
            if not detection.detected:
                return PreviewInfo(
                    sandbox_id=sandbox_id,
                    status=PreviewStatus.FAILED,
                    framework="unknown",
                )
            if not command:
                command = detection.command
            if port == 0:
                port = detection.port
            framework = detection.framework
        else:
            framework = "custom"

        # Start the app in the background inside the container
        container = self._get_container(sandbox_id)
        api = container.client.api
        exec_id = await asyncio.to_thread(
            api.exec_create,
            container.id,
            ["/bin/sh", "-c", f"cd /workspace && {command}"],
            workdir="/workspace",
        )
        await asyncio.to_thread(api.exec_start, exec_id, detach=True)

        # Health check: poll the port for up to 15 seconds
        healthy = False
        for _ in range(15):
            await asyncio.sleep(1.0)
            check = await self.execute(
                sandbox_id,
                SandboxJob(
                    command=f"curl -sf http://localhost:{port}/ -o /dev/null -w '%{{http_code}}'",
                    timeout_seconds=5,
                ),
            )
            if check.exit_code == 0:
                healthy = True
                break

        if not healthy:
            info = PreviewInfo(
                sandbox_id=sandbox_id,
                status=PreviewStatus.FAILED,
                container_port=port,
                framework=framework,
            )
            self._previews[sandbox_id] = info
            return info

        # Determine host port — read from container port bindings if available,
        # otherwise construct a proxy URL via the API server.
        # For Docker sandboxes without published ports, we route through the
        # sandbox execute endpoint as a reverse proxy.
        await asyncio.to_thread(container.reload)
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        host_port = 0
        port_key = f"{port}/tcp"
        if ports.get(port_key):
            host_port = int(ports[port_key][0].get("HostPort", 0))

        preview_url = (
            f"http://localhost:{host_port}"
            if host_port
            else f"/api/v1/sandboxes/{sandbox_id}/preview"
        )

        info = PreviewInfo(
            sandbox_id=sandbox_id,
            status=PreviewStatus.RUNNING,
            preview_url=preview_url,
            container_port=port,
            host_port=host_port,
            framework=framework,
            started_at=datetime.now(UTC),
        )
        self._previews[sandbox_id] = info
        return info

    async def stop_preview(self, sandbox_id: str) -> None:
        """Stop the preview server running inside the sandbox."""
        from lintel.sandbox.types import SandboxJob

        info = self._previews.pop(sandbox_id, None)
        if info is not None and info.container_port > 0:
            # Kill the process listening on the preview port
            await self.execute(
                sandbox_id,
                SandboxJob(
                    command=f"kill $(lsof -t -i:{info.container_port}) 2>/dev/null || true",
                    timeout_seconds=10,
                ),
            )

    async def get_preview(self, sandbox_id: str) -> PreviewInfo:
        """Return current preview info for a sandbox."""
        from lintel.sandbox.types import PreviewInfo, PreviewStatus

        info = self._previews.get(sandbox_id)
        if info is None:
            return PreviewInfo(sandbox_id=sandbox_id, status=PreviewStatus.STOPPED)
        return info

    async def destroy(self, sandbox_id: str) -> None:
        self._guards.pop(sandbox_id, None)
        self._configs.pop(sandbox_id, None)
        self._previews.pop(sandbox_id, None)
        network_name = self._networks.pop(sandbox_id, None)
        container = self._containers.pop(sandbox_id, None)
        if container is None:
            # Try to find by label (e.g. after server restart)
            try:
                client = self._get_client()
                matches = await asyncio.to_thread(
                    client.containers.list,
                    filters={"label": f"lintel.sandbox_id={sandbox_id}"},
                    all=True,
                )
                if matches:
                    container = matches[0]
            except Exception:
                # Docker not available (e.g. inside a sandbox container) — nothing to destroy
                return
        if container:
            await asyncio.to_thread(container.remove, force=True)
        # Clean up the disk-backed workspace volume
        try:
            client = self._get_client()
            vol = await asyncio.to_thread(client.volumes.get, f"lintel-workspace-{sandbox_id}")
            await asyncio.to_thread(vol.remove, force=True)
        except Exception:
            pass  # Volume may not exist or Docker unavailable
        # Clean up the per-sandbox Docker network
        if network_name is not None:
            try:
                client = self._get_client()
                net = await asyncio.to_thread(client.networks.get, network_name)
                await asyncio.to_thread(net.remove)
            except Exception:
                pass  # Network may already be removed

    async def recover_containers(self) -> list[dict[str, Any]]:
        """Re-attach to containers from previous runs using Docker labels.

        Returns a list of metadata dicts for each recovered container,
        reconstructed from Docker labels.
        """
        client = self._get_client()
        containers = await asyncio.to_thread(
            client.containers.list,
            filters={"label": "lintel.sandbox_id"},
            all=True,
        )
        recovered: list[dict[str, Any]] = []
        for container in containers:
            labels = container.labels
            sandbox_id = labels.get("lintel.sandbox_id", "")
            if sandbox_id and sandbox_id not in self._containers:
                status: str = container.status
                if status == "created":
                    # Container was never started — try to start it
                    import contextlib

                    import structlog

                    _logger = structlog.get_logger()
                    try:
                        await asyncio.to_thread(container.start)
                        chown_cmd = "chown -R vscode:vscode /workspace"
                        await asyncio.to_thread(container.exec_run, chown_cmd, user="root")
                        status = "running"
                    except Exception:
                        _logger.warning(
                            "recover_created_container_failed",
                            sandbox_id=sandbox_id[:12],
                        )
                        with contextlib.suppress(Exception):
                            await asyncio.to_thread(container.remove, force=True)
                        continue
                if status in ("running", "paused", "restarting"):
                    self._containers[sandbox_id] = container
                    recovered.append(
                        {
                            "sandbox_id": sandbox_id,
                            "image": labels.get("lintel.image", ""),
                            "network_enabled": labels.get("lintel.network_enabled") == "True",
                            "workspace_id": labels.get("lintel.workspace_id", ""),
                            "channel_id": labels.get("lintel.channel_id", ""),
                            "status": status,
                            "container_id": container.short_id,
                        }
                    )
                else:
                    # Dead/exited containers — clean up
                    await asyncio.to_thread(container.remove, force=True)
        return recovered
