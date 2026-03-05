# Web Research - Infrastructure

## Current Best Practices (2024-2025) for AI Agent Infrastructure

---

## 1. Sandbox Isolation (WEB-INFRA-01 to WEB-INFRA-06)

### WEB-INFRA-01: Container Security Landscape (2025)

The AI agent sandbox security landscape has evolved significantly:
- **Docker + seccomp + AppArmor**: Standard baseline, sufficient for most use cases
- **gVisor (runsc)**: Application kernel providing stronger isolation with ~5-15% overhead
- **Firecracker microVMs**: VM-level isolation with <125ms cold start, used by AWS Lambda
- **Kata Containers**: Lightweight VMs via QEMU, higher overhead than Firecracker

Production recommendation: Docker with defense-in-depth for v0.1, Firecracker for managed service tier.

**Confidence**: 0.90

### WEB-INFRA-02: Container Escape Mitigations

Defense-in-depth layers:
1. `--cap-drop=ALL` (remove all Linux capabilities)
2. `--security-opt=no-new-privileges` (prevent privilege escalation)
3. Read-only root filesystem (`--read-only`)
4. Non-root user (`USER 1000:1000`)
5. Seccomp profile (restrict syscalls)
6. AppArmor/SELinux profile
7. NetworkPolicy default-deny
8. Resource limits (CPU, memory, disk, PIDs)

**Confidence**: 0.90

### WEB-INFRA-03: Network Isolation for AI Sandboxes

Best practices from production AI platforms:
- Default-deny NetworkPolicy on sandbox namespace
- Allow-list only: NATS (event bus), internal registries
- No direct internet access from sandboxes
- Proxy for package installation (if needed during setup)
- DNS restriction to internal services only

**Confidence**: 0.85

### WEB-INFRA-04: Resource Limits

Recommended defaults for code execution sandboxes:
- CPU: 2 cores (soft), 4 cores (hard)
- Memory: 4 GiB (soft), 8 GiB (hard)
- Disk: 10 GiB ephemeral storage
- PIDs: 512 max
- Timeout: 30 minutes (hard kill)
- Network bandwidth: 10 Mbps

**Confidence**: 0.85

### WEB-INFRA-05: Sandbox Lifecycle Management

Production patterns:
- Pre-warm pool of base containers (reduces cold start by 60-80%)
- Garbage collection: destroy after task completion + grace period
- Orphan detection: periodic sweep for containers without active jobs
- Volume cleanup: separate from container lifecycle
- Audit: emit events for create, start, stop, destroy

**Confidence**: 0.85

### WEB-INFRA-06: Devcontainer Performance

Cold start benchmarks (2024):
- No prebuild: 2-5 minutes (image pull + build + deps)
- Prebuilt image: 10-30 seconds (pull + start)
- Warm pool: 1-5 seconds (already running)
- Local cache hit: 5-10 seconds (no pull needed)

Target for Lintel: <30s cold start (prebuilt), <5s warm start.

**Confidence**: 0.85

---

## 2. NATS JetStream (WEB-INFRA-07 to WEB-INFRA-10)

### WEB-INFRA-07: NATS JetStream Adoption

NATS JetStream has gained significant traction for event-driven architectures:
- Single binary deployment (no ZooKeeper/KRaft)
- Built-in persistence, KV store, and object store
- Native work-queue semantics (no consumer group complexity)
- Embedded NATS in Go applications gaining popularity
- Growing Python ecosystem (`nats-py` async client)

**Confidence**: 0.85

### WEB-INFRA-08: Subject Hierarchy Design

Recommended subject hierarchy for Lintel:

```
lintel.events.{tenant_id}.{aggregate_type}.{event_type}
lintel.commands.{service}.{command}
lintel.queries.{service}.{query}
```

Examples:
- `lintel.events.acme.thread.ThreadMessageReceived`
- `lintel.events.acme.sandbox.SandboxCreated`
- `lintel.commands.sandbox.create`

Design subjects before creating streams; subject hierarchy is hard to change.

**Confidence**: 0.85

### WEB-INFRA-09: Stream Partitioning

For high-throughput scenarios:
- Use multiple streams partitioned by tenant or aggregate type
- Consumer groups auto-balance across workers
- Max-in-flight controls back-pressure
- Flow control prevents slow consumers from blocking producers

**Confidence**: 0.80

### WEB-INFRA-10: NATS Monitoring and Operations

Production operations:
- `nats-top` for real-time monitoring
- Prometheus exporter for metrics
- JetStream advisories for operational alerts
- Cluster sizing: 3-node minimum for production
- Storage: file-based for durability, memory for performance-critical streams

**Confidence**: 0.85

---

## 3. Kubernetes for AI Workloads (WEB-INFRA-11 to WEB-INFRA-16)

### WEB-INFRA-11: K8s Jobs for Sandbox Execution

Best practices for using K8s Jobs for code execution:
- `backoffLimit: 0` (no retries for sandbox failures)
- `activeDeadlineSeconds` for hard timeout
- Pod security standards: `restricted` profile
- Separate namespace per tenant (or per isolation tier)
- Job labels for tracking: thread_ref, agent_id, job_type

**Confidence**: 0.90

### WEB-INFRA-12: KEDA for Event-Driven Scaling

KEDA (Kubernetes Event-Driven Autoscaling) patterns:
- Scale agent workers based on NATS consumer lag
- Scale sandbox runners based on pending job count
- Scale-to-zero during idle periods
- Custom metrics for model-specific scaling (GPU vs CPU)

**Confidence**: 0.85

### WEB-INFRA-13: Pod Security Standards

Three levels (Kubernetes 1.25+):
- **Privileged**: Unrestricted (never for sandboxes)
- **Baseline**: Prevents known privilege escalations
- **Restricted**: Heavily restricted (target for sandboxes)

Apply via namespace labels:
```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

**Confidence**: 0.90

### WEB-INFRA-14: Warm Container Pools

Pattern for reducing sandbox cold start:
- Maintain pool of pre-created pods with base image
- On job request: claim pod from pool, mount workspace volume
- Pool size based on demand prediction
- Separate pools per devcontainer config hash
- Cost trade-off: idle resources vs startup latency

**Confidence**: 0.80

### WEB-INFRA-15: Multi-Tenancy Patterns

K8s multi-tenancy for Lintel:
- **Namespace per tenant**: Simplest isolation
- **NetworkPolicy per namespace**: Network isolation
- **ResourceQuota per namespace**: Resource isolation
- **RBAC per namespace**: Access isolation
- **Separate node pools**: For strict compliance requirements

**Confidence**: 0.85

### WEB-INFRA-16: GPU Scheduling for Local Models

For tenants running local inference:
- `nvidia.com/gpu` resource requests
- Node selectors for GPU-equipped nodes
- Time-slicing for shared GPU access
- MIG (Multi-Instance GPU) for A100/H100
- Separate node pool for GPU workloads

**Confidence**: 0.80

---

## 4. Docker and CI/CD (WEB-INFRA-17 to WEB-INFRA-21)

### WEB-INFRA-17: Multi-Stage Docker Builds

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev --frozen

FROM python:3.12-slim AS runtime
RUN useradd -m -r lintel
COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
USER lintel
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["uvicorn", "lintel.api.app:app"]
```

**Confidence**: 0.90

### WEB-INFRA-18: Container Image Security

Production checklist:
- Trivy scan in CI (fail on HIGH/CRITICAL)
- Hadolint for Dockerfile linting
- SBOM generation (Syft)
- Image signing (Cosign/Notation)
- Minimal base images (distroless or slim)
- Pin base image digests, not tags

**Confidence**: 0.85

### WEB-INFRA-19: CI/CD Pipeline Stages

Recommended pipeline:
1. Lint (ruff, mypy, hadolint)
2. Unit tests (pytest, fast)
3. Build container images
4. Integration tests (testcontainers)
5. Security scan (Trivy, Grype)
6. Push to registry (content-addressable tags)
7. Deploy to staging
8. E2E tests
9. Promote to production

**Confidence**: 0.85

### WEB-INFRA-20: Docker Compose for Local Dev

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: lintel
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]

  nats:
    image: nats:2.10
    command: ["-js", "-sd", "/data"]
    ports: ["4222:4222", "8222:8222"]
    volumes: ["nats_data:/data"]

  api:
    build: .
    depends_on: [postgres, nats]
    environment:
      DATABASE_URL: postgresql://...
      NATS_URL: nats://nats:4222
    ports: ["8000:8000"]
```

**Confidence**: 0.90

### WEB-INFRA-21: Helm Best Practices

Production Helm patterns:
- Use `values.yaml` for defaults, override per environment
- Pre-install hooks for database migrations
- Rolling updates with readiness probes
- PodDisruptionBudgets for control plane services
- Separate Helm releases for control plane vs worker pool

**Confidence**: 0.85
