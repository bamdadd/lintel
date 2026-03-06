# Clean Code Analysis: Python Backend

## CLEAN-01: Duplicate SandboxManager Protocol (Critical)
**Location**: `contracts/protocols.py:137-164` vs `domain/sandbox/protocols.py:11-30`
**Severity**: Critical
**Issue**: Two Protocol definitions with incompatible signatures. Violates Single Source of Truth.
**Fix**: Delete `domain/sandbox/protocols.py`. Update `contracts/protocols.py` to use typed value objects.

## CLEAN-02: Protocol/Implementation Method Name Mismatch (Critical)
**Location**: `contracts/protocols.py` vs `infrastructure/sandbox/docker_backend.py`
**Severity**: Critical
**Issue**: Protocol defines `create_sandbox`/`execute_command`/`destroy_sandbox`. Implementation defines `create`/`execute`/`destroy`. Structural subtyping fails.
**Fix**: Align method names. Recommended: use shorter names (`create`, `execute`, `destroy`) which match industry convention.

## CLEAN-03: Redundant CommandResult Protocol
**Location**: `contracts/protocols.py:131-134`
**Severity**: Medium
**Issue**: `CommandResult` Protocol duplicates `SandboxResult` dataclass. Both have `exit_code`, `stdout`, `stderr`.
**Fix**: Remove `CommandResult`. Use `SandboxResult` everywhere.

## CLEAN-04: Missing `demux=True` in exec_run
**Location**: `infrastructure/sandbox/docker_backend.py:63-66`
**Severity**: High
**Issue**: Without `demux=True`, stderr is interleaved with stdout. `SandboxResult.stderr` is always empty string.
**Fix**: Add `demux=True` and handle the `(stdout, stderr)` tuple return.

## CLEAN-05: No Execution Timeout
**Location**: `infrastructure/sandbox/docker_backend.py:55-71`
**Severity**: High
**Issue**: No timeout on `exec_run`. A hanging command blocks the event loop thread forever.
**Fix**: Add `timeout` parameter to `SandboxJob` and pass through. Use `asyncio.wait_for` as backup.

## CLEAN-06: In-Memory Container Dict
**Location**: `infrastructure/sandbox/docker_backend.py:17`
**Severity**: High
**Issue**: `_containers: dict[str, Any]` is lost on restart. No way to recover running containers.
**Fix**: Use Docker labels for discovery. Add `recover()` or `list_active()` method.

## CLEAN-07: Missing Error Handling in execute
**Location**: `infrastructure/sandbox/docker_backend.py:62`
**Severity**: Medium
**Issue**: `self._containers[sandbox_id]` raises bare `KeyError` if ID not found.
**Fix**: Define `SandboxNotFoundError`. Check and raise with clear message.

## CLEAN-08: Docker Client Created Per-Call
**Location**: `infrastructure/sandbox/docker_backend.py:19-22`
**Severity**: Low
**Issue**: `_get_client()` creates a new Docker client on every call. Should reuse.
**Fix**: Create in `__init__` or use lazy initialization with caching.

## CLEAN-09: API Routes Disconnected
**Location**: `api/routes/sandboxes.py`
**Severity**: High
**Issue**: Routes use in-memory dict, not wired to `DockerSandboxManager` or `app.state`.
**Fix**: Wire via `request.app.state.sandbox_manager` after adding to lifespan.

## CLEAN-10: Placeholder Implement Node
**Location**: `workflows/nodes/implement.py`
**Severity**: High
**Issue**: Returns hardcoded data. No actual sandbox interaction.
**Fix**: Implement real sandbox lifecycle (create, execute, collect, destroy).

## CLEAN-11: Broken Conformance Test
**Location**: `tests/unit/contracts/test_protocols.py`
**Severity**: Medium
**Issue**: Test uses wrong method signatures. Does not detect the Protocol mismatch.
**Fix**: Write proper conformance test using `DockerSandboxManager` against canonical Protocol.

## CLEAN-12: SandboxConfig Missing Fields
**Location**: `contracts/types.py:160-165`
**Severity**: Medium
**Issue**: Only `image`, `memory_limit`, `cpu_quota`. Missing: `network_enabled`, `timeout_seconds`, `environment`, `repo_url`.
**Fix**: Extend with fields needed by both Docker and cloud backends.

## CLEAN-13: Docker Socket Exposure
**Location**: `ops/docker-compose.yaml`
**Severity**: Critical (Security)
**Issue**: `/var/run/docker.sock` mounted directly. Any container escape gives full host root access.
**Fix**: Use Docker socket proxy (Tecnativa/docker-socket-proxy) limiting to create/exec/remove operations.

## CLEAN-14: No SandboxManager in app.state
**Location**: `api/app.py:40-59`
**Severity**: High
**Issue**: `DockerSandboxManager` not instantiated in lifespan. Cannot be used by routes or workflows.
**Fix**: Add `app.state.sandbox_manager = DockerSandboxManager()` in lifespan.
