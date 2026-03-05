# Codebase Survey - Infrastructure

## Survey Context

Lintel is a greenfield project. This survey documents reference implementations and architectural patterns for the infrastructure layer.

---

## 1. Reference Architecture Patterns

### REPO-INFRA-01: Devcontainer Lifecycle Pattern
The devcontainer lifecycle (allocate, create volume, clone repo, build/pull image, run commands, collect artifacts, destroy) mirrors GitHub Codespaces and Gitpod. Use `devcontainers/cli` for programmatic control. OpenHands uses a similar Docker-based sandbox with WebSocket control channel.

### REPO-INFRA-02: Image Caching Strategy
Hash devcontainer config files, store built images in a registry. On sandbox creation, pull from cache; only rebuild on config change.

### REPO-INFRA-03: Kubernetes Node Type Mapping

| Node Type | K8s Primitive | Scaling |
|-----------|--------------|---------|
| Control plane | Deployment + Service | HPA on CPU/request rate |
| Agent workers | Deployment with KEDA | Scale on NATS queue depth |
| Sandbox runners | K8s Jobs or DaemonSet | Cluster autoscaler |
| Projection nodes | Deployment (stateless) | HPA on consumer lag |

### REPO-INFRA-04: Docker-in-Docker Options
1. **Sysbox runtime**: Rootless Docker-in-Docker without `--privileged`. Most secure.
2. **Kaniko/buildkit**: For image building only.
3. **Privileged DaemonSet with dedicated node pool**: Taint sandbox nodes.

### REPO-INFRA-05: Postgres Event Store Schema

```sql
CREATE TABLE events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id       TEXT NOT NULL,
    stream_version  BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type      TEXT NOT NULL,
    actor_id        TEXT NOT NULL,
    correlation_id  UUID NOT NULL,
    causation_id    UUID,
    payload         JSONB NOT NULL,
    payload_hash    TEXT,
    prev_hash       TEXT,
    idempotency_key TEXT,
    UNIQUE (stream_id, stream_version),
    UNIQUE (idempotency_key)
);
```

### REPO-INFRA-06: Retention Strategy
- Hot (3 months): fully indexed
- Warm (3-12 months): minimal indexes, read-only tablespace
- Cold (12+ months): export to Parquet in S3/MinIO, drop partition
- Compliance events: exempt from cold archival

### REPO-INFRA-07: NATS JetStream vs Kafka

| Criterion | NATS JetStream | Kafka |
|-----------|---------------|-------|
| Operational complexity | Low (single binary) | High |
| Latency | Sub-millisecond | Low milliseconds |
| Work-queue semantics | Built-in | Requires consumer groups |
| Request-reply | Native | Not native |
| Deployment size | Single node viable | Min 3 brokers |

**Recommendation**: NATS JetStream for v0.1.

### REPO-INFRA-08: Subject Design

```
lintel.events.{event_type}
lintel.commands.{service}.{command}
lintel.sandbox.{runner_id}.jobs
lintel.sandbox.{runner_id}.heartbeat
lintel.agents.{worker_id}.steps
```

### REPO-INFRA-09: Worker Scheduling
Capability-based scheduling with registration, heartbeat, and scoring (capability match + queue depth + affinity + residency constraints).

---

## 2. Recommended Infrastructure Layout

### REPO-INFRA-10: Docker Compose for Local Dev
Postgres, NATS, Redis, control-plane, agent-workers (x2), sandbox-runner with Docker socket.

### REPO-INFRA-11: Helm Chart Structure
Umbrella chart with per-service templates, network policies, KEDA objects.

### REPO-INFRA-12: CI/CD Pipeline
lint → unit-test → build-images → integration-test → security-scan → push-images → deploy-staging → e2e-test → deploy-production

### REPO-INFRA-13: IaC Layout
docker-compose, helm-charts, terraform modules/environments, scripts.

---

## 3. Key Infrastructure Decisions

### REPO-INFRA-14: Container Orchestration
Kubernetes recommended for Jobs API, NetworkPolicy, ecosystem.

### REPO-INFRA-15: Messaging
NATS JetStream for v0.1 on operational simplicity. Kafka migration path at scale.

### REPO-INFRA-16: Sandbox Isolation
Docker+devcontainers primary, gVisor for hardening, Firecracker for managed service.

### REPO-INFRA-17: Event Store
Postgres for SQL flexibility, JSONB, partitioning, pgvector.

### REPO-INFRA-18: Networking
K8s NetworkPolicy with default-deny for sandboxes. Linkerd optional for mTLS.

---

## 4. Security Considerations

### REPO-INFRA-19: Defense-in-Depth Sandbox Isolation
Network, runtime, filesystem, process, and DNS layers.

### REPO-INFRA-20: Secret Management
External Secrets Operator, sandbox injection pattern, PII vault separation.

### REPO-INFRA-21: Container Hardening
Distroless images, scanning, no Docker socket in sandboxes, signed images.

### REPO-INFRA-22: Resource Quotas
Per-sandbox limits, per-org ResourceQuota, rate limiting via event counting, token budgets via ModelCallCompleted projections.
