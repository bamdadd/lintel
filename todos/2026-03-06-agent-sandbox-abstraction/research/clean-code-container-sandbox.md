# Clean Code Analysis: Container & Sandbox Runtimes

## Security Hardening Gaps

### Missing seccomp Profile
**Location**: `infrastructure/sandbox/docker_backend.py:32-50`
**Severity**: Medium
**Issue**: No `--security-opt seccomp=<profile>` specified. Uses Docker default profile which allows ~300 syscalls. A tighter profile would block unnecessary syscalls.
**Fix**: Create a minimal seccomp profile allowing only required syscalls (read, write, open, exec, etc.).

### No PID Limit
**Location**: `infrastructure/sandbox/docker_backend.py:32-50`
**Severity**: Medium
**Issue**: No `--pids-limit` specified. A fork bomb inside the container could exhaust host PIDs.
**Fix**: Add `pids_limit=100` (or similar) to container create params.

### Docker Socket Privilege Escalation
**Location**: `ops/docker-compose.yaml`
**Severity**: Critical
**Issue**: Docker socket mount gives any process in the compose network full control over the Docker daemon, including ability to: mount host filesystem, create privileged containers, access host network.
**Mitigation Options**:
1. Docker socket proxy (Tecnativa/docker-socket-proxy) — restrict to specific API endpoints
2. Run sandbox manager as a sidecar with its own socket access
3. Use Docker TCP with TLS client certificates
4. For production: use a remote Docker host or switch to E2B/Modal

## Resource Management

### No Disk Space Limits
**Issue**: `tmpfs` is limited to 100MB, but if root filesystem were writable (or workspace volume mounted), no disk quota exists.
**Fix**: Use `storage_opt` for device mapper or overlay2 quota, or volume size limits.

### No Network Egress Control
**Issue**: `network_mode="none"` is all-or-nothing. Some workflows may need network access (e.g., `pip install`).
**Fix**: Add `network_enabled: bool` to `SandboxConfig`. When enabled, use a custom network with egress filtering (iptables rules or network policy).

## Lifecycle Gaps

### No Cleanup on Crash
**Issue**: If the Lintel process crashes, containers continue running with no cleanup mechanism.
**Fix**:
1. Docker labels already present — use for recovery
2. Add startup recovery: `client.containers.list(filters={"label": "lintel.sandbox_id"})` then destroy
3. Add TTL/max-age to containers via a background cleanup task

### No Health Monitoring
**Issue**: No way to detect if a container has died unexpectedly (OOM killed, etc.).
**Fix**: Add `get_status()` method that checks container state via Docker API.
