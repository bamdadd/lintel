# Streaming Sandbox Execute Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream command output (test runs, lint) line-by-line from sandbox containers to the pipeline UI in real-time, eliminating the current black-box wait during long-running commands.

**Architecture:** Add an `execute_stream()` method to the `SandboxManager` protocol that yields `(stream, line)` tuples using Docker SDK's `exec_create` + `exec_start(stream=True, demux=True)`. Workflow nodes (`_run_tests`, `_run_lint`) call `execute_stream()` and pipe each line to `tracker.append_log()`, which persists to the pipeline store immediately. The existing SSE polling endpoint (`/pipelines/{run_id}/stages/{stage_id}/logs`) already polls every 0.5s and emits new log lines — no SSE changes needed.

**Tech Stack:** Python 3.12, Docker SDK (`docker` package), asyncio, frozen dataclasses, Protocol interfaces

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `packages/contracts/src/lintel/contracts/protocols.py:191-250` | Add `execute_stream()` to `SandboxManager` protocol |
| Modify | `packages/infrastructure/src/lintel/infrastructure/sandbox/docker_backend.py:167-202` | Implement `execute_stream()` using Docker streaming exec |
| Modify | `packages/workflows/src/lintel/workflows/nodes/implement.py:1060-1146` | Rewrite `_run_tests()` to use streaming |
| Modify | `packages/workflows/src/lintel/workflows/nodes/implement.py:1149-1220` | Rewrite `_run_lint()` to use streaming |
| Modify | `packages/workflows/src/lintel/workflows/nodes/test_code.py:22-130` | Update `run_tests()` to use streaming |
| Create | `packages/contracts/tests/test_execute_stream_protocol.py` | Protocol conformance test for `execute_stream` |
| Create | `packages/infrastructure/tests/sandbox/test_docker_streaming.py` | Unit tests for Docker streaming exec (mocked) |
| Create | `packages/workflows/tests/nodes/test_streaming_tests.py` | Unit tests for streaming `_run_tests` and `_run_lint` |

---

## Chunk 1: Protocol & Docker Backend

### Task 1: Add `execute_stream` to SandboxManager protocol

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/protocols.py:200-204`
- Test: `packages/contracts/tests/test_execute_stream_protocol.py`

- [ ] **Step 1: Write the protocol conformance test**

Create `packages/contracts/tests/test_execute_stream_protocol.py`:

```python
"""Tests for execute_stream protocol method."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from lintel.contracts.protocols import SandboxManager
from lintel.contracts.types import SandboxJob, SandboxResult, SandboxStatus, ThreadRef


class FakeSandboxManager:
    """Minimal fake that satisfies SandboxManager protocol including execute_stream."""

    async def create(self, config: Any, thread_ref: ThreadRef) -> str:
        return "fake-id"

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        return SandboxResult(exit_code=0, stdout="ok", stderr="")

    async def execute_stream(
        self, sandbox_id: str, job: SandboxJob
    ) -> AsyncIterator[str]:
        yield "line 1"
        yield "line 2"

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        pass

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        from lintel.contracts.types import SandboxStatus
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


class TestExecuteStreamProtocol:
    def test_fake_satisfies_protocol(self) -> None:
        manager: SandboxManager = FakeSandboxManager()
        assert isinstance(manager, SandboxManager)

    async def test_execute_stream_yields_lines(self) -> None:
        manager = FakeSandboxManager()
        job = SandboxJob(command="echo hello", timeout_seconds=10)
        lines = [line async for line in await manager.execute_stream("fake", job)]
        assert lines == ["line 1", "line 2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_execute_stream_protocol.py -v`
Expected: FAIL — `SandboxManager` protocol doesn't have `execute_stream` yet, so the `isinstance` check may pass (structural typing) but the second test should work. The key is verifying the test infrastructure works.

- [ ] **Step 3: Add `execute_stream` to the SandboxManager protocol**

In `packages/contracts/src/lintel/contracts/protocols.py`, add the import for `AsyncIterator` to the `TYPE_CHECKING` block (it's already there at line 12), then add this method after `execute()` (after line 204):

```python
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
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_execute_stream_protocol.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/lintel/contracts/protocols.py packages/contracts/tests/test_execute_stream_protocol.py
git commit -m "feat(contracts): add execute_stream to SandboxManager protocol"
```

---

### Task 2: Implement `execute_stream` in DockerSandboxManager

**Files:**
- Modify: `packages/infrastructure/src/lintel/infrastructure/sandbox/docker_backend.py:167-202`
- Create: `packages/infrastructure/tests/sandbox/test_docker_streaming.py`

- [ ] **Step 1: Write tests for Docker streaming exec**

Create `packages/infrastructure/tests/sandbox/test_docker_streaming.py`:

```python
"""Tests for DockerSandboxManager.execute_stream (mocked Docker API)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.contracts.types import SandboxJob
from lintel.infrastructure.sandbox.docker_backend import DockerSandboxManager


def _make_manager_with_container(
    exec_output: list[tuple[bytes | None, bytes | None]],
    exit_code: int = 0,
) -> tuple[DockerSandboxManager, str]:
    """Create a DockerSandboxManager with a mocked container."""
    manager = DockerSandboxManager()

    mock_container = MagicMock()
    mock_api = MagicMock()

    # exec_create returns an exec id
    mock_api.exec_create.return_value = {"Id": "exec-123"}

    # exec_start(stream=True, demux=True) returns an iterator of (stdout, stderr) chunks
    mock_api.exec_start.return_value = iter(exec_output)

    # exec_inspect returns exit code
    mock_api.exec_inspect.return_value = {"ExitCode": exit_code}

    mock_container.client.api = mock_api
    mock_container.id = "container-abc"

    sandbox_id = "test-sandbox"
    manager._containers[sandbox_id] = mock_container

    return manager, sandbox_id


class TestExecuteStream:
    async def test_streams_stdout_lines(self) -> None:
        manager, sandbox_id = _make_manager_with_container(
            exec_output=[
                (b"line 1\nline 2\n", None),
                (b"line 3\n", None),
            ],
            exit_code=0,
        )
        job = SandboxJob(command="make test", timeout_seconds=60)

        lines: list[str] = []
        async for line in await manager.execute_stream(sandbox_id, job):
            lines.append(line)

        assert "line 1" in lines
        assert "line 2" in lines
        assert "line 3" in lines
        assert lines[-1] == "__EXIT:0__"

    async def test_streams_stderr_lines(self) -> None:
        manager, sandbox_id = _make_manager_with_container(
            exec_output=[
                (None, b"error 1\nerror 2\n"),
            ],
            exit_code=1,
        )
        job = SandboxJob(command="make test", timeout_seconds=60)

        lines: list[str] = []
        async for line in await manager.execute_stream(sandbox_id, job):
            lines.append(line)

        assert "error 1" in lines
        assert "error 2" in lines
        assert lines[-1] == "__EXIT:1__"

    async def test_interleaved_stdout_stderr(self) -> None:
        manager, sandbox_id = _make_manager_with_container(
            exec_output=[
                (b"out 1\n", b"err 1\n"),
                (b"out 2\n", None),
            ],
            exit_code=0,
        )
        job = SandboxJob(command="make test", timeout_seconds=60)

        lines: list[str] = []
        async for line in await manager.execute_stream(sandbox_id, job):
            lines.append(line)

        assert "out 1" in lines
        assert "err 1" in lines
        assert "out 2" in lines

    async def test_partial_lines_buffered(self) -> None:
        """Lines that don't end with newline are buffered until next chunk."""
        manager, sandbox_id = _make_manager_with_container(
            exec_output=[
                (b"partial", None),
                (b" complete\n", None),
            ],
            exit_code=0,
        )
        job = SandboxJob(command="echo test", timeout_seconds=60)

        lines: list[str] = []
        async for line in await manager.execute_stream(sandbox_id, job):
            lines.append(line)

        # "partial" and " complete" should be joined into one line
        assert "partial complete" in lines

    async def test_empty_output(self) -> None:
        manager, sandbox_id = _make_manager_with_container(
            exec_output=[],
            exit_code=0,
        )
        job = SandboxJob(command="true", timeout_seconds=60)

        lines: list[str] = []
        async for line in await manager.execute_stream(sandbox_id, job):
            lines.append(line)

        assert lines == ["__EXIT:0__"]

    async def test_timeout_raises(self) -> None:
        """Streaming should respect job timeout."""
        import asyncio

        manager, sandbox_id = _make_manager_with_container(
            exec_output=[],
            exit_code=0,
        )

        # Make the blocking iterator hang
        def slow_iter() -> Any:
            import time
            time.sleep(5)
            yield (b"late\n", None)

        manager._containers[sandbox_id].client.api.exec_start.return_value = slow_iter()

        job = SandboxJob(command="sleep 100", timeout_seconds=1)

        with pytest.raises(Exception):  # SandboxTimeoutError
            async for _ in await manager.execute_stream(sandbox_id, job):
                pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/infrastructure/tests/sandbox/test_docker_streaming.py -v`
Expected: FAIL — `execute_stream` not implemented yet

- [ ] **Step 3: Implement `execute_stream` in DockerSandboxManager**

In `packages/infrastructure/src/lintel/infrastructure/sandbox/docker_backend.py`, add this method after the existing `execute()` method (after line 202):

```python
    async def execute_stream(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> AsyncIterator[str]:
        """Execute a command and yield output lines as they arrive.

        Uses Docker exec API with streaming enabled. Yields individual lines
        from combined stdout/stderr. The final yield is ``__EXIT:<code>__``.
        """
        from collections.abc import AsyncIterator

        from lintel.contracts.errors import SandboxTimeoutError

        container = self._get_container(sandbox_id)

        api = container.client.api
        exec_id = api.exec_create(
            container.id,
            cmd=["/bin/sh", "-c", job.command],
            workdir=job.workdir or "/workspace",
        )

        # exec_start with stream=True returns a blocking generator of chunks.
        # We run it in a thread to avoid blocking the event loop.
        output_gen = api.exec_start(exec_id, stream=True, demux=True)

        async def _stream() -> AsyncIterator[str]:
            import asyncio

            stdout_buf = ""
            stderr_buf = ""

            def _next_chunk() -> tuple[bytes | None, bytes | None] | None:
                try:
                    return next(output_gen)
                except StopIteration:
                    return None

            while True:
                try:
                    chunk = await asyncio.wait_for(
                        asyncio.to_thread(_next_chunk),
                        timeout=job.timeout_seconds,
                    )
                except TimeoutError:
                    raise SandboxTimeoutError(
                        f"Command timed out after {job.timeout_seconds}s: {job.command}"
                    )

                if chunk is None:
                    # Stream ended — flush remaining buffers
                    if stdout_buf.strip():
                        yield stdout_buf
                    if stderr_buf.strip():
                        yield stderr_buf
                    break

                stdout_bytes, stderr_bytes = chunk

                if stdout_bytes:
                    stdout_buf += stdout_bytes.decode("utf-8", errors="replace")
                    while "\n" in stdout_buf:
                        line, stdout_buf = stdout_buf.split("\n", 1)
                        if line.strip():
                            yield line

                if stderr_bytes:
                    stderr_buf += stderr_bytes.decode("utf-8", errors="replace")
                    while "\n" in stderr_buf:
                        line, stderr_buf = stderr_buf.split("\n", 1)
                        if line.strip():
                            yield line

            # Get exit code
            inspect = api.exec_inspect(exec_id)
            exit_code = inspect.get("ExitCode", -1)
            yield f"__EXIT:{exit_code}__"

        return _stream()
```

Also add the `AsyncIterator` import at the top of the file. In the `from __future__ import annotations` section, the type is already string-quoted. Add to the existing `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from collections.abc import AsyncIterator  # add this line
    from lintel.contracts.types import (
        ...
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/infrastructure/tests/sandbox/test_docker_streaming.py -v`
Expected: PASS

- [ ] **Step 5: Run contracts tests to ensure no regressions**

Run: `make test-contracts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/sandbox/docker_backend.py packages/infrastructure/tests/sandbox/test_docker_streaming.py
git commit -m "feat(sandbox): implement execute_stream for real-time command output"
```

---

## Chunk 2: Streaming Test & Lint Execution in Workflow Nodes

### Task 3: Create helper to consume streaming execute with log forwarding

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/implement.py`
- Create: `packages/workflows/tests/nodes/test_streaming_tests.py`

The key insight: we need a helper that consumes `execute_stream()`, forwards each line to `tracker.append_log()`, collects all output, and returns `(full_output, exit_code)` — same signature as the current blocking approach but with real-time logging.

- [ ] **Step 1: Write tests for the streaming helper**

Create `packages/workflows/tests/nodes/test_streaming_tests.py`:

```python
"""Tests for streaming test/lint execution in implement node."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeStreamingSandbox:
    """Fake sandbox manager that supports execute_stream."""

    def __init__(self, lines: list[str], exit_code: int = 0) -> None:
        self._lines = lines
        self._exit_code = exit_code

    async def execute(self, sandbox_id: str, job: Any) -> Any:
        from lintel.contracts.types import SandboxResult
        return SandboxResult(exit_code=0, stdout="ok", stderr="")

    async def execute_stream(self, sandbox_id: str, job: Any) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            for line in self._lines:
                yield line
            yield f"__EXIT:{self._exit_code}__"
        return _gen()

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        pass

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []


class TestStreamExecuteWithLogging:
    async def test_collects_output_and_exit_code(self) -> None:
        from lintel.workflows.nodes.implement import _stream_execute_with_logging

        sandbox = FakeStreamingSandbox(["line 1", "line 2"], exit_code=0)
        logged: list[str] = []

        async def log_fn(line: str) -> None:
            logged.append(line)

        output, exit_code = await _stream_execute_with_logging(
            sandbox, "fake-id", "make test", "/workspace", 300, log_fn,
        )
        assert exit_code == 0
        assert "line 1" in output
        assert "line 2" in output
        assert logged == ["line 1", "line 2"]

    async def test_failed_exit_code(self) -> None:
        from lintel.workflows.nodes.implement import _stream_execute_with_logging

        sandbox = FakeStreamingSandbox(["FAILED: test_foo"], exit_code=1)
        logged: list[str] = []

        async def log_fn(line: str) -> None:
            logged.append(line)

        output, exit_code = await _stream_execute_with_logging(
            sandbox, "fake-id", "make test", "/workspace", 300, log_fn,
        )
        assert exit_code == 1
        assert "FAILED: test_foo" in output
        assert logged == ["FAILED: test_foo"]

    async def test_fallback_to_blocking_execute(self) -> None:
        """If sandbox doesn't support execute_stream, fall back to execute()."""
        from lintel.workflows.nodes.implement import _stream_execute_with_logging

        # Sandbox without execute_stream
        sandbox = MagicMock()
        sandbox.execute_stream = None  # explicitly no streaming
        sandbox.execute = AsyncMock(return_value=MagicMock(
            exit_code=0, stdout="blocking output\n", stderr="",
        ))

        logged: list[str] = []

        async def log_fn(line: str) -> None:
            logged.append(line)

        output, exit_code = await _stream_execute_with_logging(
            sandbox, "fake-id", "make test", "/workspace", 300, log_fn,
        )
        assert exit_code == 0
        assert "blocking output" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/workflows/tests/nodes/test_streaming_tests.py -v`
Expected: FAIL — `_stream_execute_with_logging` doesn't exist yet

- [ ] **Step 3: Implement `_stream_execute_with_logging` helper**

Add this function to `packages/workflows/src/lintel/workflows/nodes/implement.py`, after the imports section (around line 40, before `implement_code`):

```python
async def _stream_execute_with_logging(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    command: str,
    workdir: str,
    timeout_seconds: int,
    log_fn: Callable[[str], Awaitable[None]],
) -> tuple[str, int]:
    """Execute a command with real-time log streaming.

    If the sandbox supports ``execute_stream()``, yields lines to ``log_fn``
    as they arrive. Otherwise falls back to blocking ``execute()`` and logs
    output after completion.

    Returns ``(full_output, exit_code)`` — same contract as the old blocking path.
    """
    from lintel.contracts.types import SandboxJob

    stream_fn = getattr(sandbox_manager, "execute_stream", None)
    if stream_fn is None or not callable(stream_fn):
        # Fallback: blocking execute
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=command, workdir=workdir, timeout_seconds=timeout_seconds),
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            stripped = line.strip()
            if stripped:
                await log_fn(stripped)
        return output, result.exit_code

    # Streaming path
    job = SandboxJob(command=command, workdir=workdir, timeout_seconds=timeout_seconds)
    output_lines: list[str] = []
    exit_code = -1

    async for line in await stream_fn(sandbox_id, job):
        if line.startswith("__EXIT:") and line.endswith("__"):
            exit_code = int(line[7:-2])
        else:
            output_lines.append(line)
            await log_fn(line)

    return "\n".join(output_lines), exit_code
```

Add the necessary imports near the top of the file:

```python
from collections.abc import Awaitable, Callable
```

(Check if `Awaitable` and `Callable` are already imported; if so, skip.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/workflows/tests/nodes/test_streaming_tests.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/implement.py packages/workflows/tests/nodes/test_streaming_tests.py
git commit -m "feat(workflows): add _stream_execute_with_logging helper"
```

---

### Task 4: Wire streaming into `_run_tests`

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/implement.py:1060-1146`

- [ ] **Step 1: Rewrite `_run_tests` to use streaming**

Replace the test execution block in `_run_tests` (lines 1123-1146). The function currently does:

```python
    await tracker.append_log("implement", f"Running tests: {test_command[:80]}")
    try:
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=test_command, workdir=workspace_path, timeout_seconds=600),
        )
    except Exception:
        ...

    output = result.stdout + result.stderr
    verdict = "PASSED" if result.exit_code == 0 else "FAILED"
    await tracker.append_log("implement", f"Tests: {verdict}")
    for line in output.splitlines()[-30:]:
        ...
```

Replace with:

```python
    await tracker.append_log("implement", f"Running tests: {test_command[:80]}")

    async def _log_test_line(line: str) -> None:
        await tracker.append_log("implement", line)

    try:
        output, exit_code = await _stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            test_command,
            workspace_path,
            600,
            _log_test_line,
        )
    except Exception:
        logger.warning("implement_test_execute_failed")
        return "Test execution failed", 1

    verdict = "PASSED" if exit_code == 0 else "FAILED"
    await tracker.append_log("implement", f"Tests: {verdict}")

    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    return output, exit_code
```

Note: remove the old `for line in output.splitlines()[-30:]` block — lines are already logged in real-time by the streaming helper.

- [ ] **Step 2: Run affected tests**

Run: `make test-workflows`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/implement.py
git commit -m "feat(implement): stream test output in real-time"
```

---

### Task 5: Wire streaming into `_run_lint`

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/implement.py:1149-1220`

- [ ] **Step 1: Rewrite lint execution to use streaming**

Replace the lint execution block in `_run_lint` (lines 1196-1220). Currently:

```python
    await tracker.append_log("implement", f"Running lint: {lint_command[:80]}")
    try:
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=lint_command, workdir=workspace_path, timeout_seconds=120),
        )
    except Exception:
        ...

    output = result.stdout + result.stderr
    verdict = "PASSED" if result.exit_code == 0 else "FAILED"
    ...
```

Replace with:

```python
    await tracker.append_log("implement", f"Running lint: {lint_command[:80]}")

    async def _log_lint_line(line: str) -> None:
        await tracker.append_log("implement", line)

    try:
        output, exit_code = await _stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            lint_command,
            workspace_path,
            120,
            _log_lint_line,
        )
    except Exception:
        logger.warning("implement_lint_execute_failed")
        return "Lint execution failed", 1

    verdict = "PASSED" if exit_code == 0 else "FAILED"
    await tracker.append_log("implement", f"Lint: {verdict}")

    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    return output, exit_code
```

- [ ] **Step 2: Run affected tests**

Run: `make test-workflows`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/implement.py
git commit -m "feat(implement): stream lint output in real-time"
```

---

### Task 6: Wire streaming into `test_code.py` node

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/test_code.py:95-130`

- [ ] **Step 1: Update test_code node to use streaming**

The `test_code.py` `run_tests()` function has a similar blocking pattern. Replace the test execution section (around lines 95-130) to use `_stream_execute_with_logging` from the implement module:

```python
    from lintel.workflows.nodes.implement import _stream_execute_with_logging

    await tracker.append_log("test", f"Running: {test_command}")

    async def _log_test_line(line: str) -> None:
        await tracker.append_log("test", line)

    try:
        output, exit_code = await _stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            test_command,
            workspace_path,
            600,
            _log_test_line,
        )
    except Exception:
        logger.warning("test_execute_failed")
        return {"error": "Test execution failed", "test_verdict": "error", "test_output": ""}

    await tracker.append_log("test", f"Exit code: {exit_code}")
```

Remove the old `for line in output.splitlines()` log-after-the-fact block.

- [ ] **Step 2: Run affected tests**

Run: `make test-workflows`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/test_code.py
git commit -m "feat(test-node): stream test output in real-time"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

Run: `make test-unit`
Expected: PASS

- [ ] **Step 2: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: PASS

- [ ] **Step 3: Final commit if any fixes needed**

---

## Notes

### Backward Compatibility

The `_stream_execute_with_logging` helper gracefully falls back to blocking `execute()` if the sandbox manager doesn't have `execute_stream`. This means:
- In-memory/fake sandboxes in tests continue to work unchanged
- Any custom SandboxManager implementations that haven't added `execute_stream` won't break

### Log Volume

Streaming every line of test output could create large log arrays in the pipeline store. The current SSE endpoint polls every 0.5s and only emits new lines since the last poll — this is efficient. However, if test output is very verbose (thousands of lines), consider adding a line-rate limiter in `_stream_execute_with_logging` (e.g., batch every 10 lines into one log entry). This is a future optimization — start without it.

### Exit Code Sentinel

The `__EXIT:<code>__` sentinel pattern is simple and unambiguous. It avoids needing a separate RPC call or return channel. The streaming consumer knows the stream is done when it sees this sentinel.
