# Framework Documentation - Infrastructure

## Documentation Sources

Official documentation for infrastructure components referenced in Lintel's architecture.

---

## 1. Devcontainers (DOCS-INFRA-01 to DOCS-INFRA-05)

### DOCS-INFRA-01: devcontainer.json Specification

```json
{
  "name": "lintel-sandbox",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/git:1": {},
    "ghcr.io/devcontainers/features/node:1": {}
  },
  "postCreateCommand": "pip install -r requirements.txt",
  "remoteUser": "vscode",
  "customizations": {
    "vscode": { "extensions": ["ms-python.python"] }
  }
}
```

### DOCS-INFRA-02: devcontainer CLI

```bash
# Build image
devcontainer build --workspace-folder .

# Start container
devcontainer up --workspace-folder . --id-label sandbox_id=abc123

# Execute command
devcontainer exec --workspace-folder . -- python -m pytest

# Read configuration
devcontainer read-configuration --workspace-folder .
```

The CLI is the programmatic interface Lintel uses to manage sandbox containers.

### DOCS-INFRA-03: Devcontainer Features

Features are shareable units of installation code:
- Install tools, runtimes, or configure settings
- Composable: multiple features per container
- Published to OCI registries (ghcr.io)
- Lintel can publish custom features for common sandbox setups

### DOCS-INFRA-04: Devcontainer Lifecycle Hooks

Execution order:
1. `initializeCommand` — runs on host before container starts
2. `onCreateCommand` — runs once when container is created
3. `updateContentCommand` — runs when content changes
4. `postCreateCommand` — runs after create + updateContent
5. `postStartCommand` — runs every time container starts
6. `postAttachCommand` — runs when client attaches

For Lintel sandboxes: use `onCreateCommand` for repo setup, `postCreateCommand` for dependency install.

### DOCS-INFRA-05: Prebuild Caching

```bash
# Build and tag by config hash
CONFIG_HASH=$(sha256sum .devcontainer/devcontainer.json | cut -c1-12)
devcontainer build --workspace-folder . --image-name registry/sandbox:${CONFIG_HASH}
docker push registry/sandbox:${CONFIG_HASH}
```

Prebuild images in CI. Tag by hash of devcontainer config. Pull instead of build at runtime.

---

## 2. Kubernetes (DOCS-INFRA-06 to DOCS-INFRA-13)

### DOCS-INFRA-06: Jobs for Sandbox Execution

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: sandbox-${JOB_ID}
  labels:
    lintel.io/sandbox: "true"
    lintel.io/thread: "${THREAD_REF}"
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 1800
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: sandbox
          image: registry/sandbox:${CONFIG_HASH}
          resources:
            limits:
              cpu: "2"
              memory: 4Gi
              ephemeral-storage: 10Gi
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
```

### DOCS-INFRA-07: NetworkPolicy Default-Deny

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-default-deny
  namespace: lintel-sandboxes
spec:
  podSelector:
    matchLabels:
      lintel.io/sandbox: "true"
  policyTypes: ["Ingress", "Egress"]
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: nats
      ports:
        - port: 4222
```

### DOCS-INFRA-08: ResourceQuota per Namespace

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: sandbox-quota
  namespace: lintel-sandboxes
spec:
  hard:
    requests.cpu: "32"
    requests.memory: 64Gi
    limits.cpu: "64"
    limits.memory: 128Gi
    count/jobs.batch: "20"
```

### DOCS-INFRA-09: RBAC for Sandbox Service Account

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sandbox-manager
  namespace: lintel-sandboxes
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "delete"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
```

### DOCS-INFRA-10: KEDA Autoscaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: agent-worker-scaler
spec:
  scaleTargetRef:
    name: agent-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
    - type: nats-jetstream
      metadata:
        natsServerMonitoringEndpoint: "nats:8222"
        account: "$G"
        stream: "lintel-commands"
        consumer: "agent-workers"
        lagThreshold: "10"
```

### DOCS-INFRA-11: Health Probes

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /readyz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### DOCS-INFRA-12: ConfigMap and Secrets

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lintel-config
data:
  NATS_URL: "nats://nats:4222"
  EVENT_STORE_DSN: "postgresql://..."
---
apiVersion: v1
kind: Secret
metadata:
  name: lintel-secrets
type: Opaque
data:
  SLACK_BOT_TOKEN: <base64>
  ANTHROPIC_API_KEY: <base64>
```

### DOCS-INFRA-13: Helm Chart Structure

```
charts/lintel/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── statefulset-nats.yaml
│   ├── job-migrations.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── service.yaml
│   ├── networkpolicy.yaml
│   ├── resourcequota.yaml
│   └── rbac.yaml
```

---

## 3. NATS JetStream (DOCS-INFRA-14 to DOCS-INFRA-19)

### DOCS-INFRA-14: Stream Configuration

```
nats stream add LINTEL-EVENTS \
  --subjects "lintel.events.>" \
  --storage file \
  --retention limits \
  --max-msgs=-1 \
  --max-bytes=10GB \
  --max-age=90d \
  --replicas=3 \
  --discard=old
```

Subject hierarchy: `lintel.events.{tenant}.{aggregate}.{event_type}`

### DOCS-INFRA-15: Durable Consumers

```
nats consumer add LINTEL-EVENTS projection-thread-view \
  --filter "lintel.events.*.thread.*" \
  --deliver=all \
  --ack=explicit \
  --max-deliver=5 \
  --max-pending=1000
```

### DOCS-INFRA-16: Key-Value Store

```python
kv = await js.key_value(bucket="lintel-thread-state")
await kv.put("thread:abc123", json.dumps(state).encode())
entry = await kv.get("thread:abc123")
state = json.loads(entry.value)
```

NATS KV is useful for lightweight state lookups (thread routing, agent status).

### DOCS-INFRA-17: Request-Reply Pattern

```python
# Worker subscribes to command subjects
sub = await nc.subscribe("lintel.commands.sandbox.create")
async for msg in sub.messages:
    result = await create_sandbox(msg.data)
    await msg.respond(result)

# Requester
response = await nc.request("lintel.commands.sandbox.create", payload, timeout=30)
```

### DOCS-INFRA-18: NATS vs Kafka Comparison

| Feature | NATS JetStream | Kafka |
|---------|---------------|-------|
| Operational complexity | Low (single binary) | High (ZK/KRaft + brokers) |
| Work-queue semantics | Native | Requires consumer groups |
| KV store | Built-in | Requires external |
| Protocol | NATS protocol | Custom binary |
| Throughput | ~1M msg/s | ~2M msg/s |
| Ecosystem | Growing | Mature |
| Best for | v0.1 simplicity | Scale-out production |

### DOCS-INFRA-19: Monitoring

NATS exposes HTTP monitoring at port 8222:
- `/varz` - server stats
- `/jsz` - JetStream stats
- `/connz` - connections
- Prometheus exporter available via `nats-exporter`

---

## 4. PostgreSQL (DOCS-INFRA-20 to DOCS-INFRA-24)

### DOCS-INFRA-20: Table Partitioning

```sql
CREATE TABLE events (
    event_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    ...
) PARTITION BY RANGE (occurred_at);

CREATE TABLE events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

Monthly partitions. Automate partition creation via pg_partman or a scheduled job.

### DOCS-INFRA-21: LISTEN/NOTIFY for Event Bridge

```sql
-- Trigger on event insert
CREATE OR REPLACE FUNCTION notify_new_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_event', NEW.event_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER event_inserted AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION notify_new_event();
```

```python
# Python consumer (dedicated non-pooled connection)
conn = await asyncpg.connect(dsn)
await conn.add_listener('new_event', handle_notification)
```

Important: Use a dedicated connection for LISTEN, not a pooled one (PgBouncer drops notifications).

### DOCS-INFRA-22: JSONB Indexing

```sql
-- Index on event_type within payload
CREATE INDEX idx_events_type ON events ((payload->>'event_type'));

-- GIN index for flexible querying
CREATE INDEX idx_events_payload_gin ON events USING GIN (payload);
```

### DOCS-INFRA-23: Connection Pooling

Use PgBouncer in transaction mode for general queries. Keep a separate direct connection for:
- LISTEN/NOTIFY
- Advisory locks
- Prepared statements (if needed)

### DOCS-INFRA-24: Backup and WAL Archiving

```bash
# Continuous archiving
archive_mode = on
archive_command = 'aws s3 cp %p s3://lintel-wal-archive/%f'

# Point-in-time recovery
restore_command = 'aws s3 cp s3://lintel-wal-archive/%f %p'
recovery_target_time = '2026-03-05 12:00:00'
```

For compliance: WAL archiving enables point-in-time recovery and audit trail preservation.
