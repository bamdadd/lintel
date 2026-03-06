# Web Research: Container & Sandbox Runtimes

## Docker Container Security for AI Agents (2024-2025)

### Key Sources
- [WEB-03] Trail of Bits — "Container Security for AI" (2025) — recommends gVisor/Firecracker for untrusted code
- [WEB-06] OWASP — "AI Agent Security" (2025) — sandbox isolation requirements
- [WEB-13] Docker Blog — "Securing Containers for AI Workloads" (2024)

### Consensus
- Standard Docker (runc) shares host kernel — insufficient for untrusted AI-generated code in multi-tenant.
- Acceptable for single-user dev/test environments with hardened config.
- Production multi-tenant: use gVisor (runsc), Firecracker microVMs, or managed services (E2B, Modal).

### Hardening Checklist
1. `cap_drop=["ALL"]` — drop all capabilities
2. `read_only=True` — read-only root filesystem
3. `network_mode="none"` — no network (or filtered egress)
4. `user="1000:1000"` — non-root
5. `no-new-privileges:true` — prevent privilege escalation
6. `pids_limit=100` — prevent fork bombs
7. `mem_limit` — prevent OOM
8. `cpu_quota` — prevent CPU monopolization
9. Custom seccomp profile — minimize syscall surface
10. No Docker socket mount — prevent container escape

## E2B vs Docker vs Modal for Agent Sandboxes

### E2B
- **Isolation**: Firecracker microVMs (strongest)
- **Cold start**: ~300ms
- **File I/O**: Native API (fast, reliable)
- **Pricing**: Pay-per-second, $0.0001/s
- **Use case**: Multi-tenant SaaS, production AI agents

### Docker (local)
- **Isolation**: Shared kernel (weakest)
- **Cold start**: ~500ms-2s
- **File I/O**: tar archives or exec (slower)
- **Pricing**: Free (self-hosted)
- **Use case**: Development, single-tenant, testing

### Modal
- **Isolation**: gVisor (strong)
- **Cold start**: ~1s (warm) to ~5s (cold)
- **File I/O**: Network filesystem
- **Pricing**: Pay-per-second, $0.000016/GPU-s
- **Use case**: GPU workloads, compute-intensive agents

### Daytona
- **Isolation**: Container-based with VM option
- **Cold start**: ~2-5s
- **File I/O**: Workspace API
- **Pricing**: Open source (self-hosted)
- **Use case**: Development environments, devcontainer support

## Devcontainer in Agent Workflows

### Pattern
1. Agent receives repo URL
2. Check for `.devcontainer/devcontainer.json`
3. If present: use devcontainer CLI to build and run
4. If absent: use default `SandboxConfig.image`
5. Execute commands via `devcontainer exec` or Docker SDK

### Benefits
- Reproducible environments
- Project-specific tooling pre-installed
- Industry standard (VS Code, GitHub Codespaces, Gitpod)

### Drawbacks
- Slower cold start (build step)
- Larger images
- Devcontainer CLI required as dependency
