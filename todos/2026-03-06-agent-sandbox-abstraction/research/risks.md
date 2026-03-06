# Risks & Troubleshooting

## F.1 Risk Analysis

### Risk 1: Docker Socket Privilege Escalation (Critical)
**Description**: `/var/run/docker.sock` mounted in `docker-compose.yaml` gives full host root access to any process that can reach it.
**Likelihood**: Medium (requires container escape or compromised service)
**Impact**: Critical (full host compromise)
**Detection**: Audit docker-compose.yaml mounts; monitor Docker API calls
**Mitigation**:
1. Use Docker socket proxy (Tecnativa/docker-socket-proxy) limiting to create/exec/remove
2. Run sandbox manager as isolated sidecar
3. For production: use remote Docker host or E2B/Modal
**Fallback**: Accept risk for dev/test; mandate cloud backend for production
**Evidence**: [CLEAN-13, REPO-13]

### Risk 2: Protocol/Implementation Mismatch (Critical)
**Description**: `DockerSandboxManager` does not satisfy `SandboxManager` Protocol. Any code using the Protocol type will get `AttributeError` at runtime.
**Likelihood**: Certain (bug exists today)
**Impact**: High (sandbox unusable through Protocol)
**Detection**: mypy strict mode (if properly wired), runtime AttributeError
**Mitigation**: This is the primary deliverable — consolidate Protocol and fix implementation
**Evidence**: [CLEAN-01, CLEAN-02, REPO-01, REPO-04, REPO-05]

### Risk 3: In-Memory Container State Loss (High)
**Description**: `_containers: dict[str, Any]` is lost on process restart. Running containers become orphans.
**Likelihood**: High (any restart/crash)
**Impact**: Medium (resource leak, orphan containers)
**Detection**: Docker labels on containers; periodic cleanup check
**Mitigation**:
1. Add startup recovery: `client.containers.list(filters={"label": "lintel.sandbox_id"})`
2. Destroy orphans on startup
3. Add TTL/max-age cleanup background task
**Evidence**: [CLEAN-06]

### Risk 4: Silent Stderr Loss (Medium)
**Description**: Without `demux=True`, stderr is interleaved with stdout. Error messages from tools/tests are mixed with output.
**Likelihood**: Certain (bug exists today)
**Impact**: Medium (debugging difficulty, agent confusion)
**Detection**: Test that stderr field is populated
**Mitigation**: Add `demux=True` to `exec_run` calls
**Evidence**: [CLEAN-04, DOCS-03]

### Risk 5: No Execution Timeouts (Medium)
**Description**: No timeout on `execute()`. A hanging command (infinite loop, deadlock) blocks the asyncio thread indefinitely.
**Likelihood**: Medium (AI-generated code can have infinite loops)
**Impact**: High (thread pool exhaustion, service degradation)
**Detection**: Monitor thread pool saturation; per-command duration alerts
**Mitigation**:
1. Add `timeout_seconds` to `SandboxJob`
2. Use `asyncio.wait_for` wrapping `to_thread`
3. Docker `exec_run` supports timeout (but kills the exec, not the process)
**Evidence**: [CLEAN-05]

### Risk 6: Docker Tar API Complexity (Low)
**Description**: File I/O via `put_archive`/`get_archive` requires tar archive construction/extraction. More complex than shell commands.
**Likelihood**: Low (well-documented API)
**Impact**: Low (implementation complexity, not runtime risk)
**Detection**: Unit tests for file operations
**Mitigation**: Encapsulate tar handling in helper functions; test with various file types
**Evidence**: [DOCKER-03]

### Risk 7: Cloud Backend Integration Gaps (Low)
**Description**: Protocol designed from Docker perspective may not map cleanly to E2B/Modal APIs.
**Likelihood**: Low (industry convergence means APIs are similar)
**Impact**: Medium (adapter complexity)
**Detection**: Implement E2B backend and verify Protocol fit
**Mitigation**: Protocol uses generic operations (execute, read_file, write_file) that all providers support
**Evidence**: [E2B-03, WEB-09]

## F.2 Common Issues & Solutions

### Issue: Container Stays Running After Error
**Symptom**: Containers accumulate, consuming resources
**Cause**: No `async with` lifecycle management; exceptions skip `destroy()`
**Solution**: Use `sandbox_session()` async context manager for all sandbox usage

### Issue: exec_run Returns Combined Output
**Symptom**: `SandboxResult.stderr` is always empty; stdout contains error messages
**Cause**: Missing `demux=True` parameter
**Solution**: `container.exec_run(cmd, demux=True)` returns `(stdout, stderr)` tuple

### Issue: Write File to Read-Only Container
**Symptom**: `PermissionError` when writing files
**Cause**: `read_only=True` in container create
**Solution**: Mount a writable volume at `/workspace`; keep root filesystem read-only

### Issue: Network Access Needed for pip install
**Symptom**: `pip install` fails with connection errors
**Cause**: `network_mode="none"` blocks all network access
**Solution**: Use `network_enabled` config flag; create with network during setup phase, then disconnect

## F.3 Testing Considerations

### What Needs Testing
- Protocol conformance (structural subtyping check)
- Sandbox lifecycle (create, execute, destroy)
- File I/O operations (read, write, list)
- Error handling (not found, timeout, execution failure)
- Stderr capture (demux=True verification)
- Concurrent sandbox operations

### Testing Strategy
- **Unit tests**: `DummySandboxManager` implementing Protocol with in-memory state
- **Integration tests**: Real Docker containers via testcontainers
- **Conformance tests**: Verify `DockerSandboxManager` satisfies `SandboxManager` Protocol

### DummySandboxManager for Unit Tests
```python
class DummySandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxResult(exit_code=0, stdout="ok")

    # ... remaining methods
```
