# Clean Code Analysis - Infrastructure

## Standards for Lintel's Infrastructure Layer

---

## 1. Infrastructure as Code

- **CLEAN-INFRA-01**: Docker Compose for local dev, Helm/K8s for production
- **CLEAN-INFRA-02**: Reproducible builds — content-addressable tags, locked dependencies, hermetic builds
- **CLEAN-INFRA-03**: Environment parity via config-only diffs between dev/staging/prod
- **CLEAN-INFRA-04**: External secrets operator; no secrets in images or Helm values
- **CLEAN-INFRA-05**: Strict config hierarchy: defaults < config file < env var < secret store

## 2. Container Best Practices

- **CLEAN-INFRA-06**: Multi-stage Docker builds for all services
- **CLEAN-INFRA-07**: Minimal base images (`python:3.12-slim`), non-root user
- **CLEAN-INFRA-08**: Security scanning in CI (Trivy/Grype/Hadolint), SBOM generation
- **CLEAN-INFRA-09**: Mandatory resource limits on all containers
- **CLEAN-INFRA-10**: Health/readiness probes (`/healthz`, `/readyz`) on every service

## 3. Sandbox Security

- **CLEAN-INFRA-11**: Default-deny NetworkPolicy with allow-list egress
- **CLEAN-INFRA-12**: Ephemeral volumes, read-only root filesystem, writable only `/workspace` and `/tmp`
- **CLEAN-INFRA-13**: Resource limits: max 2 CPU, 4 GiB RAM, 10 GiB disk, 30-min timeout
- **CLEAN-INFRA-14**: No privilege escalation, `--cap-drop=ALL`, seccomp profile
- **CLEAN-INFRA-15**: Full audit logging of sandbox lifecycle events

## 4. Event Store Operations

- **CLEAN-INFRA-16**: Append-only Postgres table with INSERT-only role
- **CLEAN-INFRA-17**: Indexes: event_id (unique), stream composite, event_type, correlation_id, occurred_at
- **CLEAN-INFRA-18**: Monthly time-range partitioning
- **CLEAN-INFRA-19**: WAL archiving, configurable retention (default 2 years)
- **CLEAN-INFRA-20**: Versioned event types with upcasting projections

## 5. Anti-Patterns

- **CLEAN-INFRA-21**: No shared mutable state between sandboxes
- **CLEAN-INFRA-22**: No missing resource limits (CI lint enforcement)
- **CLEAN-INFRA-23**: No hardcoded configuration (scan in CI)
- **CLEAN-INFRA-24**: No missing health checks
- **CLEAN-INFRA-25**: Structured JSON logging with correlation IDs and OpenTelemetry propagation
