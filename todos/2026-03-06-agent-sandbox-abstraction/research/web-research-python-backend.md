# Web Research: Python Backend

## Protocol vs ABC for Python Service Boundaries (2024-2025)

### Consensus
- `typing.Protocol` (PEP 544) is the preferred approach for defining service boundaries in modern Python.
- ABCs require explicit inheritance; Protocols use structural subtyping ("duck typing with type checking").
- MyPy and Pyright fully support Protocol checking.
- FastAPI ecosystem favors Protocol-based DI.

### Key Sources
- [WEB-01] Python docs — typing.Protocol official documentation
- [WEB-02] Real Python — "Protocols and Structural Subtyping in Python" (2024)
- [WEB-03] Hynek Schlawack — "Subclassing and Composition" (2024) — argues for Protocol over ABC

## Frozen Dataclasses Best Practices

### Pattern
```python
@dataclass(frozen=True, slots=True)
class SandboxConfig:
    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
```

- `frozen=True` — immutable, hashable, thread-safe
- `slots=True` — memory efficient, prevents attribute typos
- Default values for optional config
- Use `frozenset` for collection fields (not `list`)

### Lintel Observation
- Lintel uses `frozen=True` but not `slots=True` on most types.
- `SandboxConfig` fields are adequate for Docker; need extension for cloud backends.

## asyncio.to_thread Best Practices

### When to Use
- Wrapping synchronous SDK calls (Docker SDK, file I/O, subprocess).
- Should NOT be used for CPU-bound work (use ProcessPoolExecutor instead).

### Common Pattern
```python
async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
    container = self._containers[sandbox_id]
    result = await asyncio.to_thread(
        container.exec_run,
        cmd=job.command,
        workdir=job.workdir or "/workspace",
        demux=True,
    )
    stdout, stderr = result.output
    return SandboxResult(
        exit_code=result.exit_code,
        stdout=(stdout or b"").decode("utf-8", errors="replace"),
        stderr=(stderr or b"").decode("utf-8", errors="replace"),
    )
```

## Exception Hierarchy for Domain Errors

### Pattern
```python
class SandboxError(Exception):
    """Base for all sandbox errors."""

class SandboxNotFoundError(SandboxError):
    """Sandbox ID not found."""

class SandboxExecutionError(SandboxError):
    """Command execution failed."""

class SandboxTimeoutError(SandboxError):
    """Command or creation timed out."""
```

- Place in `contracts/` since they're part of the Protocol's contract.
- Catch in workflow nodes for clean error handling.
