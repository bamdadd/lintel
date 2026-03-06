# Framework Docs: Container & Sandbox Runtimes

## E2B SDK

### Sandbox Lifecycle
```python
from e2b_code_interpreter import AsyncSandbox

# Create with context manager (recommended)
async with await AsyncSandbox.create() as sandbox:
    result = await sandbox.commands.run("echo hello")
    print(result.stdout)
# Automatically destroyed

# Or manual lifecycle
sandbox = await AsyncSandbox.create()
try:
    result = await sandbox.commands.run("python script.py")
finally:
    await sandbox.close()
```

### Command Execution
```python
result = await sandbox.commands.run(
    cmd="pytest tests/",
    timeout=60,  # seconds
    cwd="/workspace",
    envs={"CI": "true"},
)
# result.exit_code, result.stdout, result.stderr
```

### File Operations (Native)
```python
# Write file
await sandbox.files.write("/workspace/main.py", "print('hello')")

# Read file
content = await sandbox.files.read("/workspace/main.py")

# List directory
entries = await sandbox.files.list("/workspace")
```

### Key Design Decisions
- Sandbox ID is a string (UUID)
- All operations are async
- File I/O is native (not shell-based) — faster and handles encoding correctly
- Sandboxes have configurable timeouts and auto-destroy
- Supports custom Docker images (Dockerfiles)

## Devcontainer Specification

### `devcontainer.json`
```json
{
    "image": "mcr.microsoft.com/devcontainers/python:3.12",
    "features": {
        "ghcr.io/devcontainers/features/node:1": {}
    },
    "postCreateCommand": "pip install -r requirements.txt",
    "remoteUser": "vscode"
}
```

### CLI Usage
```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . -- pytest
```

### Integration Pattern
- Read `.devcontainer/devcontainer.json` from repo
- Use `devcontainer` CLI to build and run
- Execute commands via `devcontainer exec`
- Alternative: parse config and use Docker SDK directly

## Testcontainers (for Testing)

### Pattern
```python
from testcontainers.core.container import DockerContainer

with DockerContainer("python:3.12-slim") as container:
    result = container.exec("python -c 'print(1+1)'")
```

### Relevance
- Lintel already uses testcontainers for PostgreSQL and NATS in integration tests.
- Could use similar pattern for sandbox testing.
- `testcontainers` is not suitable for production sandbox management — too slow, no security hardening.

## gVisor / Firecracker (Production Isolation)

### gVisor (runsc)
- User-space kernel that intercepts syscalls
- Drop-in replacement for runc: `docker run --runtime=runsc`
- Used by GCP Cloud Run, Modal
- ~5-10% overhead vs runc

### Firecracker
- MicroVM with dedicated kernel per sandbox
- Sub-second cold start (~125ms)
- Used by AWS Lambda, E2B, Vercel
- Strongest isolation (full VM boundary)
- More complex to operate than gVisor
