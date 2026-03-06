# Codebase Survey: Container & Sandbox Runtimes

## Docker Backend Implementation

### `src/lintel/infrastructure/sandbox/docker_backend.py`

**Security Configuration** (create method, lines 32-50):
```python
container = await asyncio.to_thread(
    client.containers.create,
    image=config.image,
    command="sleep infinity",
    detach=True,
    cap_drop=["ALL"],
    security_opt=["no-new-privileges:true"],
    read_only=True,
    network_mode="none",
    mem_limit=config.memory_limit,
    cpu_period=100000,
    cpu_quota=config.cpu_quota,
    user="1000:1000",
    tmpfs={"/tmp": "size=100m,noexec"},
    labels={
        "lintel.sandbox_id": sandbox_id,
        "lintel.thread_ref": thread_ref.stream_id,
    },
)
```

**Security Strengths**:
- All capabilities dropped (`cap_drop=["ALL"]`)
- Read-only root filesystem
- No network access (`network_mode="none"`)
- Non-root user (1000:1000)
- No privilege escalation (`no-new-privileges:true`)
- Memory limited (`mem_limit`)
- CPU throttled (`cpu_period` + `cpu_quota`)
- tmpfs with `noexec`
- Labels for tracking (good for recovery)

**Security Gaps**:
- No seccomp profile specified (uses Docker default)
- No AppArmor/SELinux profile
- No PID limit (`--pids-limit`)
- Docker socket exposure in `docker-compose.yaml` undermines all isolation

**Execute Method** (lines 55-71):
```python
exec_result = await asyncio.to_thread(
    container.exec_run,
    cmd=job.command,
    workdir=job.workdir or "/workspace",
)
return SandboxResult(
    exit_code=exec_result.exit_code,
    stdout=exec_result.output.decode("utf-8", errors="replace"),
)
```

Issues:
- Missing `demux=True` — stdout and stderr are combined
- No timeout parameter
- No error handling (KeyError if sandbox_id not found)
- `stderr` field never populated

**Collect Artifacts** (lines 73-80):
- Runs `git diff` and returns raw output
- No structured artifact format
- No file listing or archive support

**Destroy Method** (lines 82-85):
- `container.remove(force=True)` — correct
- Removes from in-memory dict
- No event emission

## Docker Compose Configuration

### `ops/docker-compose.yaml`
- Docker socket mounted: `/var/run/docker.sock:/var/run/docker.sock`
- This gives full root access to the host — defeats sandbox isolation
- Should use Docker socket proxy (e.g., Tecnativa/docker-socket-proxy) or sidecar pattern

## Container State Management
- `_containers: dict[str, Any]` — in-memory only
- Lost on process restart
- Labels on containers enable recovery via `client.containers.list(filters={"label": "lintel.sandbox_id=..."})`
- No `get_status()` method to query container state

## File I/O Capabilities
- Currently: none exposed in Protocol
- Docker SDK supports: `container.put_archive(path, data)` and `container.get_archive(path)`
- Requires tar archive construction/extraction
- Alternative: `exec_run("cat ...")` for reads, `exec_run("tee ...")` for writes (fragile)
