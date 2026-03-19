"""OpenShell-based sandbox backend wrapping the ``openshell`` CLI.

NVIDIA OpenShell (https://github.com/NVIDIA/OpenShell) provides policy-enforced
sandboxed environments.  This backend shells out to the ``openshell`` CLI because
the project does not expose a Python SDK.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import shutil
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.sandbox.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus


async def _run_cli(
    *args: str,
    timeout: float = 120,
    check: bool = True,
) -> tuple[int, str, str]:
    """Run an ``openshell`` CLI command and return (exit_code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "openshell",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise SandboxTimeoutError(
            f"openshell command timed out after {timeout}s: openshell {' '.join(args)}"
        ) from exc

    exit_code = proc.returncode or 0
    stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
    stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

    if check and exit_code != 0:
        raise SandboxExecutionError(
            f"openshell command failed (exit {exit_code}): {stderr or stdout}"
        )
    return exit_code, stdout, stderr


class OpenShellSandboxManager:
    """Implements ``SandboxManager`` protocol using NVIDIA OpenShell.

    Each sandbox is an OpenShell sandbox instance identified by a generated name.
    The mapping from our internal ``sandbox_id`` to the OpenShell sandbox name is
    kept in ``_sandboxes``.
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, str] = {}  # sandbox_id -> openshell sandbox name
        self._verified = False

    async def _ensure_openshell(self) -> None:
        """Verify that ``openshell`` CLI is available on PATH."""
        if self._verified:
            return
        if shutil.which("openshell") is None:
            raise SandboxExecutionError(
                "openshell CLI not found on PATH. Install it with: uv tool install -U openshell"
            )
        self._verified = True

    def _get_name(self, sandbox_id: str) -> str:
        name = self._sandboxes.get(sandbox_id)
        if name is None:
            raise SandboxNotFoundError(sandbox_id)
        return name

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str:
        await self._ensure_openshell()

        sandbox_id = str(uuid4())
        name = f"lintel-{sandbox_id[:12]}"

        create_args = ["sandbox", "create", "--name", name]

        # Pass image if not the default
        if config.image and config.image != "lintel-sandbox:latest":
            create_args.extend(["--from", config.image])

        # GPU passthrough is not configurable per-sandbox in the current CLI,
        # but we include the flag if the config has high CPU quota (heuristic).
        if config.cpu_quota > 200000:
            create_args.append("--gpu")

        await _run_cli(*create_args, timeout=config.timeout_seconds)
        self._sandboxes[sandbox_id] = name
        return sandbox_id

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult:
        from lintel.sandbox.types import SandboxResult

        name = self._get_name(sandbox_id)

        # Use SSH exec to run commands inside the sandbox
        exit_code, stdout, stderr = await _run_cli(
            "sandbox",
            "exec",
            name,
            "--",
            "/bin/sh",
            "-c",
            job.command,
            timeout=job.timeout_seconds,
            check=False,
        )
        return SandboxResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    async def execute_stream(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> AsyncIterator[str]:
        """Execute a command and yield output lines as they arrive.

        Falls back to non-streaming execution since the OpenShell CLI does not
        provide a streaming exec primitive.  Yields lines from the combined
        output followed by an ``__EXIT:<code>__`` sentinel.
        """
        result = await self.execute(sandbox_id, job)

        async def _lines() -> AsyncIterator[str]:
            combined = result.stdout + result.stderr
            for line in combined.splitlines():
                if line.strip():
                    yield line
            yield f"__EXIT:{result.exit_code}__"

        return _lines()

    async def read_file(self, sandbox_id: str, path: str) -> str:
        from lintel.sandbox.types import SandboxJob

        result = await self.execute(
            sandbox_id,
            SandboxJob(command=f"cat {shlex.quote(path)}", timeout_seconds=30),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to read {path}: {result.stderr}")
        return result.stdout

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        import tempfile

        from lintel.sandbox.types import SandboxJob

        name = self._get_name(sandbox_id)

        # Ensure parent directory exists
        dest_dir = "/".join(path.rsplit("/", 1)[:-1]) or "/"
        await self.execute(
            sandbox_id,
            SandboxJob(command=f"mkdir -p {shlex.quote(dest_dir)}", timeout_seconds=10),
        )

        # Write to a local temp file and upload via openshell sandbox upload
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            await _run_cli("sandbox", "upload", name, tmp_path, path, timeout=30)
        finally:
            import os

            os.unlink(tmp_path)

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        from lintel.sandbox.types import SandboxJob

        result = await self.execute(
            sandbox_id,
            SandboxJob(command=f"ls -1 {shlex.quote(path)}", timeout_seconds=10),
        )
        if result.exit_code != 0:
            raise SandboxExecutionError(f"Failed to list {path}: {result.stderr}")
        return [f for f in result.stdout.strip().split("\n") if f]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        from lintel.sandbox.types import SandboxStatus

        name = self._get_name(sandbox_id)

        exit_code, stdout, _stderr = await _run_cli("sandbox", "get", name, check=False, timeout=15)

        if exit_code != 0:
            return SandboxStatus.FAILED

        # Parse JSON output from `openshell sandbox get`
        lowered = stdout.lower()
        if "running" in lowered or "ready" in lowered:
            return SandboxStatus.RUNNING
        if "creating" in lowered or "provisioning" in lowered:
            return SandboxStatus.CREATING
        if "error" in lowered or "failed" in lowered:
            return SandboxStatus.FAILED
        if "deleting" in lowered:
            return SandboxStatus.DESTROYED
        return SandboxStatus.RUNNING

    async def get_logs(self, sandbox_id: str, tail: int = 200) -> str:
        name = self._get_name(sandbox_id)
        _exit_code, stdout, _stderr = await _run_cli(
            "logs", name, "--tail", str(tail), check=False, timeout=15
        )
        return stdout

    async def collect_artifacts(
        self, sandbox_id: str, workdir: str = "/workspace"
    ) -> dict[str, Any]:
        from lintel.sandbox.types import SandboxJob

        # Same git-based artifact collection as Docker backend
        find_result = await self.execute(
            sandbox_id,
            SandboxJob(
                command=f"find {workdir} -name .git -type d -maxdepth 3 2>/dev/null | head -1",
                timeout_seconds=10,
            ),
        )
        git_dir = find_result.stdout.strip()
        repo_dir = git_dir.rsplit("/.git", 1)[0] if git_dir else workdir

        await self.execute(
            sandbox_id,
            SandboxJob(command="git add -A", workdir=repo_dir, timeout_seconds=10),
        )

        exclude = "':!*.lock' ':!package-lock.json' ':!uv.lock' ':!bun.lock'"
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
        """Network policy is managed by OpenShell policies, not per-sandbox toggles."""

    async def disconnect_network(self, sandbox_id: str) -> None:
        """Network policy is managed by OpenShell policies, not per-sandbox toggles."""

    async def destroy(self, sandbox_id: str) -> None:
        name = self._sandboxes.pop(sandbox_id, None)
        if name is None:
            return
        await _run_cli("sandbox", "delete", name, check=False, timeout=30)

    async def recover_sandboxes(self) -> list[dict[str, Any]]:
        """Attempt to recover sandboxes from a previous run via ``openshell sandbox list``.

        Returns metadata dicts for any sandbox whose name starts with ``lintel-``.
        """
        try:
            _exit_code, stdout, _stderr = await _run_cli(
                "sandbox", "list", "--output", "json", check=False, timeout=15
            )
        except (SandboxExecutionError, FileNotFoundError):
            return []

        recovered: list[dict[str, Any]] = []
        try:
            sandboxes = json.loads(stdout) if stdout.strip() else []
        except json.JSONDecodeError:
            return []

        for sb in sandboxes if isinstance(sandboxes, list) else []:
            name = sb.get("name", "")
            if not name.startswith("lintel-"):
                continue
            # Reconstruct sandbox_id from the name suffix
            sandbox_id = name.removeprefix("lintel-")
            status = sb.get("status", "").lower()
            if status in ("running", "ready", "provisioning"):
                self._sandboxes[sandbox_id] = name
                recovered.append(
                    {
                        "sandbox_id": sandbox_id,
                        "image": sb.get("image", ""),
                        "network_enabled": True,
                        "workspace_id": "",
                        "channel_id": "",
                        "status": status,
                        "backend": "openshell",
                    }
                )
        return recovered
