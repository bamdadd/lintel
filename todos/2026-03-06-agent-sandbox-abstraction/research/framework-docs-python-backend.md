# Framework Docs: Python Backend

## typing.Protocol (PEP 544)

### Structural Subtyping
- Classes satisfy a Protocol if they have the required methods/attributes — no explicit `register()` or inheritance needed.
- `@runtime_checkable` decorator enables `isinstance()` checks but only verifies method existence, not signatures.
- Lintel convention: all service boundaries defined as Protocols in `contracts/protocols.py`.

### Best Practices
- Use `TYPE_CHECKING` guards for Protocol imports in implementation files.
- Protocol methods should use `...` (Ellipsis) as body — not `pass` or `raise NotImplementedError`.
- Return types must match exactly for structural conformance.
- Use `@dataclass(frozen=True)` for Protocol method parameter types.

## asyncio Patterns

### `asyncio.to_thread`
- Wraps synchronous calls (Docker SDK) in a thread pool executor.
- Returns an awaitable — caller uses `await`.
- Thread-safe for Docker SDK which uses `requests` (thread-safe HTTP client).

### Async Context Managers
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def sandbox_session(manager, config, thread_ref):
    sandbox_id = await manager.create(config, thread_ref)
    try:
        yield sandbox_id
    finally:
        await manager.destroy(sandbox_id)
```
- `__aenter__` / `__aexit__` for class-based.
- `@asynccontextmanager` for function-based.
- Essential for sandbox lifecycle — prevents container leaks.

## FastAPI Dependency Injection

### Lifespan Pattern
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sandbox_manager = DockerSandboxManager()
    yield
    # cleanup
```

### Route Access
```python
async def create_sandbox(request: Request):
    manager = request.app.state.sandbox_manager
    ...
```

## Docker SDK (docker-py)

### Key APIs
- `client.containers.create(**kwargs)` — create without starting
- `container.start()` — start container
- `container.exec_run(cmd, demux=True)` — execute command, split stdout/stderr
- `container.put_archive(path, data)` — write tar archive to container
- `container.get_archive(path)` — read tar archive from container
- `container.remove(force=True)` — stop and remove
- `client.containers.list(filters={"label": "key=value"})` — find by labels

### `demux=True` (Critical)
Without `demux=True`, `exec_run` returns interleaved stdout+stderr as a single bytes object.
With `demux=True`, returns `(stdout_bytes, stderr_bytes)` tuple.

### File Transfer
```python
import io, tarfile

# Write file to container
def write_file(container, path, content):
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        data = content.encode('utf-8')
        info = tarfile.TarInfo(name=os.path.basename(path))
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tar_stream.seek(0)
    container.put_archive(os.path.dirname(path), tar_stream)

# Read file from container
def read_file(container, path):
    bits, stat = container.get_archive(path)
    stream = io.BytesIO(b"".join(bits))
    with tarfile.open(fileobj=stream) as tar:
        member = tar.getmembers()[0]
        return tar.extractfile(member).read().decode()
```
