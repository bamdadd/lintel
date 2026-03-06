# Implementation Context

## D.1 Proposed Protocol (Option B)

### Consolidated SandboxManager Protocol
```python
class SandboxManager(Protocol):
    """Manages isolated sandbox environments for agent code execution."""

    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str: ...  # returns sandbox_id

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult: ...

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

    async def collect_artifacts(
        self,
        sandbox_id: str,
    ) -> dict[str, Any]: ...

    async def destroy(
        self,
        sandbox_id: str,
    ) -> None: ...
```

### Extended Types
```python
@dataclass(frozen=True)
class SandboxConfig:
    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_quota: int = 50000
    network_enabled: bool = False
    timeout_seconds: int = 3600
    environment: frozenset[tuple[str, str]] = frozenset()

@dataclass(frozen=True)
class SandboxJob:
    command: str
    workdir: str | None = None
    timeout_seconds: int = 300
```

### Exception Hierarchy
```python
class SandboxError(Exception): ...
class SandboxNotFoundError(SandboxError): ...
class SandboxTimeoutError(SandboxError): ...
class SandboxExecutionError(SandboxError): ...
```

## D.2 Required Refactors

### R-001: Delete Duplicate Protocol
**Location**: `domain/sandbox/protocols.py`
**Complexity**: XS
**Action**: Delete entire file. All references should point to `contracts/protocols.py`.

### R-002: Replace Contracts Protocol
**Location**: `contracts/protocols.py:131-164`
**Complexity**: S
**Action**: Remove `CommandResult` Protocol. Replace `SandboxManager` with consolidated version (see D.1).

### R-003: Extend SandboxConfig
**Location**: `contracts/types.py:160-165`
**Complexity**: XS
**Action**: Add `network_enabled`, `timeout_seconds`, `environment` fields.

### R-004: Extend SandboxJob
**Location**: `contracts/types.py:168-173`
**Complexity**: XS
**Action**: Add `timeout_seconds` field.

### R-005: Fix DockerSandboxManager
**Location**: `infrastructure/sandbox/docker_backend.py`
**Complexity**: M
**Actions**:
- Add `demux=True` to `exec_run`
- Implement `read_file` (via `get_archive` + tar extraction)
- Implement `write_file` (via tar creation + `put_archive`)
- Implement `list_files` (via `exec_run("ls -1")`)
- Implement `get_status` (via Docker container inspect)
- Add `SandboxNotFoundError` checks
- Add timeout support
- Cache Docker client

### R-006: Wire SandboxManager in Lifespan
**Location**: `api/app.py:40-59`
**Complexity**: XS
**Action**: Add `app.state.sandbox_manager = DockerSandboxManager()` in lifespan.

### R-007: Connect Sandbox Routes
**Location**: `api/routes/sandboxes.py`
**Complexity**: S
**Action**: Replace in-memory dict with `request.app.state.sandbox_manager`.

### R-008: Add sandbox_id to State
**Location**: `workflows/state.py`
**Complexity**: XS
**Action**: Add `sandbox_id: str | None` to `ThreadWorkflowState`.

### R-009: Implement Workflow Node
**Location**: `workflows/nodes/implement.py`
**Complexity**: M
**Action**: Replace placeholder with real sandbox lifecycle (create, execute, collect, destroy).

### R-010: Fix Conformance Test
**Location**: `tests/unit/contracts/test_protocols.py`
**Complexity**: S
**Action**: Write proper conformance test using `DockerSandboxManager` against canonical Protocol.

### R-011: Add Exception Types
**Location**: `contracts/` (new file or in types.py)
**Complexity**: XS
**Action**: Define `SandboxError`, `SandboxNotFoundError`, `SandboxTimeoutError`.

## D.3 Migration Considerations

### What Changes
1. `contracts/protocols.py` — new `SandboxManager` Protocol (breaking change to unused interface)
2. `contracts/types.py` — extended `SandboxConfig` and `SandboxJob` (backward compatible, new fields have defaults)
3. `infrastructure/sandbox/docker_backend.py` — 4 new methods, bug fixes
4. `api/app.py` — add sandbox manager to lifespan
5. `api/routes/sandboxes.py` — use real manager instead of in-memory dict
6. `workflows/state.py` — add `sandbox_id` field
7. `workflows/nodes/implement.py` — real implementation

### What Stays the Same
- `SandboxResult` — no changes needed
- `SandboxStatus` — already complete
- Sandbox events — already defined
- Event sourcing pattern — unchanged
- All other Protocols — unaffected

### Backward Compatibility
- The contracts-layer `SandboxManager` Protocol is currently dead code (nothing calls it correctly)
- Changing it has zero runtime impact
- `SandboxConfig` extensions use default values — existing usage unaffected

### Suggested Implementation Order
1. Types + exceptions (XS) — foundation
2. Protocol consolidation (S) — single source of truth
3. DockerSandboxManager fixes (M) — satisfy Protocol
4. Conformance test (S) — verify satisfaction
5. App wiring (XS) — make it available
6. Route integration (S) — expose via API
7. Workflow integration (M) — close the loop
