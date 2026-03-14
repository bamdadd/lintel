# lintel-sandbox

Docker-based isolated code execution sandbox with defense-in-depth security.

## Key exports

- `DockerSandboxManager` — implements `SandboxManager` protocol; creates/destroys Docker containers, executes commands, reads/writes files, streams output via `AsyncIterator`; recovers containers by label after server restart
- `_tar_helpers` — internal helpers for packing/unpacking file trees via tar streams (not part of public API)

## Dependencies

- `lintel-contracts` — `SandboxConfig`, `SandboxJob`, `SandboxResult`, `SandboxStatus`, `ThreadRef`, error types
- `docker` (python-docker SDK, runtime import), `httpx>=0.28`, `structlog>=24.4`

## Tests

```bash
make test-sandbox   # requires Docker and the sandbox image to be built
# build image first: make sandbox-image
# or: uv run pytest packages/sandbox/tests/ -v
```

## Usage

```python
from lintel.sandbox.docker_backend import DockerSandboxManager

mgr = DockerSandboxManager()
sandbox_id = await mgr.create(config)
result = await mgr.execute(sandbox_id, job)
async for chunk in mgr.stream_execute(sandbox_id, job):
    print(chunk)
await mgr.destroy(sandbox_id)
```
