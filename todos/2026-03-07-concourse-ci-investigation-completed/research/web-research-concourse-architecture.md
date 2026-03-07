# Web Research - Concourse CI Architecture

## Executive Summary

Concourse CI is a container-based automation platform built around three primitives — resources (versioned external artifacts), jobs (build plans), and tasks (containerized work units). The ATC is its central brain: web UI, REST API, and all scheduling logic backed only by PostgreSQL. A version-resolution algorithm determines what inputs a job should consume and only triggers new builds when previously-unused trigger-able versions are detected. The resource interface is a clean three-script contract (check/in/out in `/opt/resource/`) communicating via stdin/stdout JSON — an abstraction that maps naturally onto AI agent tool-calling.

## Core Architecture: ATC, TSA, Workers, Garden, BaggageClaim

- **ATC ("All Things CI")**: Port 8080. Four sub-components: Checker (LIDAR scanner — polls resources), Scheduler (10-second interval; resolves input versions; PostgreSQL locking for distributed coordination), Build Tracker (dispatches work to workers), Garbage Collector.
- **TSA**: Port 2222. Custom SSH server for worker registration. Reverse-tunnel mode for firewalled workers. Heartbeats every 30 seconds.
- **Workers**: Stateless execution nodes. Run Garden (port 7777, container lifecycle) and BaggageClaim (port 7788, volume management).
- **Single-node**: All components can run on one machine. `concourse quickstart` or Docker Compose. Only external dependency is PostgreSQL.
- **Multi-ATC**: Shared PostgreSQL; DB-level locking ensures one scheduler per tick; no ZooKeeper/etcd/Kafka needed.

## Pipeline Model

- **Pipeline schema**: `jobs` (required), `resources`, `resource_types`, `var_sources`, `groups` (UI-only), `display`
- **Variable substitution**: `((param_name))` — no loops or conditionals by design
- **Step types**: core (`get`, `put`, `task`, `set_pipeline`, `load_var`), composite (`do`, `in_parallel`), control flow (`try`, `ensure`, `on_success`, `on_failure`, `on_abort`, `on_error`)
- **Step modifiers**: `timeout`, `attempts` (retry), `tags` (worker routing), `across` (matrix execution)
- **Job config**: `serial`, `serial_groups`, `max_in_flight`, `interruptible`

## Scheduling Model

- **The Algorithm**: Version-matching engine, not time-based cron. Three resolvers:
  1. `individualResolver`: `get` steps without `passed` constraints — picks latest version
  2. `groupResolver`: `get` steps with `passed` constraints — finds versions that passed upstream jobs
  3. `pinnedResolver`: pinned resources — forces specific version
- **Trigger decision**: New build only when `trigger: true` resource has version not used by previous build
- **Resource check interval**: Default 1 minute; `check_every: never` for webhook-only

## Resource Abstraction (check/in/out)

- Container image with three executables at `/opt/resource/{check,in,out}`
- All communication is JSON over stdin/stdout
- **`check`**: Input `{"source": {...}, "version": {...}}` → Output: array of version objects (oldest first)
- **`in`**: `$1` = destination dir. Input includes params → Output: `{"version": {...}, "metadata": [...]}`
- **`out`**: `$1` = build source dir. Input includes params → Output: same as `in`. Must be idempotent.
- **Version objects**: Arbitrary JSON with string-only values
- **Proposed "Prototypes" redesign**: Arbitrary message-passing; non-linear versioning — maps better to AI interactions

## Task Execution

- Tasks run in fresh containers on workers
- Config: `platform`, `image_resource`, `inputs`, `outputs`, `caches`, `run` command, `params`
- Caches scoped to worker; no cross-worker sharing
- Privileged configured at step level, not task config
- Artifact flow: `get` outputs → task inputs → `put` steps via BaggageClaim volumes

## Build Plan Tree

- Tree structure: nodes are steps, edges are control flow
- Evaluated depth-first, left-to-right by default
- `in_parallel` for concurrent branches with `limit` and `fail_fast`
- Step hooks (`on_success`, `on_failure`, `ensure`) attach as subtrees

## API Design

- Undocumented REST API on port 8080 (GitHub issue #771)
- Web UI (Elm SPA) consumes same API
- Auth: Dex/Skymarshal for OAuth2/OIDC with JWT bearer tokens
- Key endpoints: pipeline CRUD, job triggers, `GET /api/v1/builds/:id/events` (SSE streaming)

## Single-Node vs. Multi-Node

- Single-node works for dev and small teams; no architectural reason to distribute for small deployments
- PostgreSQL is the ONLY coordination layer — no message queue needed
- Production scale reference: BOSH project — 4 ATC nodes, 34 workers, 134 teams, 534 pipelines

## Debugging

- `fly intercept`: interactive shell into build step containers
- Failed containers preserved until next build runs
- `fly watch`: stream/replay logs via SSE
- `fly rerun-build`: same input versions, new execution

## Key Patterns for Lintel

1. **Version-flow model**: Resources emit versions; jobs consume/produce them; scheduler triggers on new versions
2. **Build plan step modifiers**: `ensure`/`on_failure`/`try`/`in_parallel` — essential for production workflows
3. **PostgreSQL as only coordination**: No message queues needed for scheduling
4. **Narrow interface contracts**: check/in/out maps to Lintel's skill interfaces
5. **Separation of definition from execution**: Pipeline defines intent; ATC decides when; workers decide how

## Sources

- https://concourse-ci.org/internals.html
- https://concourse-ci.org/scheduler.html
- https://concourse-ci.org/docs/internals/scheduler/
- https://concourse-ci.org/docs/resource-types/implementing/
- https://concourse-ci.org/docs/tasks/
- https://concourse-ci.org/pipelines.html
- https://concourse-ci.org/steps.html
- https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/concourse-for-tanzu/7-0/tanzu-concourse/architecture.html
- https://blog.concourse-ci.org/posts/2019-10-15-reinventing-resource-types/
