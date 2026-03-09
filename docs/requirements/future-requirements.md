# Future Requirements

**Project:** Lintel — AI Collaboration Infrastructure Platform
**Date:** March 2026

---

## REQ-001: LLM Caching

**Stack:** LangGraph + Ollama (local inference)

### Overview

Two distinct caching layers should be implemented for any LangGraph + Ollama agent deployment:

1. **Response caching** — cache LLM outputs so repeated or similar calls skip inference entirely
2. **KV / prefix caching** — keep the model and its computed attention state warm between requests, avoiding redundant prefill computation

### Layer 1: Response Caching (LangChain built-in)

LangChain's global cache intercepts all LLM calls automatically. Set it once at startup — no changes to graph or node code required.

#### Options (in order of recommendation)

| Backend | Use case | Notes |
|---|---|---|
| `SQLiteCache` | Single-process, persistent | Zero infra, good for dev and single-node deployments |
| `RedisCache` | Multi-process / distributed | Required if running multiple agent workers |
| `RedisSemanticCache` | Fuzzy / semantic matching | Uses embeddings to match similar (not just identical) prompts |
| `InMemoryCache` | Ephemeral / testing only | Lost on restart |

#### Implementation

```python
from langchain.globals import set_llm_cache
from langchain.cache import SQLiteCache  # swap for RedisCache if distributed

set_llm_cache(SQLiteCache(database_path=".langchain.db"))
```

Call this **once at application startup**, before any LangGraph graph is compiled or invoked.

#### Semantic caching (optional upgrade)

```python
from langchain.cache import RedisSemanticCache
from langchain_ollama import OllamaEmbeddings

set_llm_cache(
    RedisSemanticCache(
        redis_url="redis://localhost:6379",
        embedding=OllamaEmbeddings(model="nomic-embed-text"),
        score_threshold=0.2  # tune for precision vs recall
    )
)
```

### Layer 2: KV / Prefix Cache Warmth (Ollama)

Ollama (via llama.cpp) maintains a KV cache per loaded model. By default, the model unloads after each request. The `keep_alive` parameter prevents this, keeping both the model weights and computed KV state in memory between calls.

This is especially valuable in agent loops where the same large system prompt is prepended to every node call — the prefix only needs to be computed once per session.

#### Implementation

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3.2",
    keep_alive="30m"  # keep model + KV cache warm for 30 minutes
)
```

#### Tuning `keep_alive`

| Value | Behaviour |
|---|---|
| `"0"` | Unload immediately after request (default) |
| `"5m"` | Keep warm for 5 minutes |
| `"30m"` | Recommended for interactive agent sessions |
| `"-1"` | Keep loaded indefinitely (until Ollama restarts) |

Set based on expected gap between requests. For long-running agent workflows, `"30m"` or higher is appropriate.

### Layer 3: Advanced — vLLM with Automatic Prefix Caching

If Ollama's prefix caching is insufficient (e.g. large shared system prompts across many concurrent sessions), **vLLM** provides production-grade automatic prefix caching with a LangChain-compatible OpenAI-style API.

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="llama3.2",
    base_url="http://localhost:8000/v1",  # vLLM server
    api_key="none"
)
```

vLLM handles prefix cache sharing across requests automatically — no application-level changes needed beyond pointing at the vLLM endpoint.

### Recommended Minimal Setup

```python
from langchain.globals import set_llm_cache
from langchain.cache import SQLiteCache
from langchain_ollama import ChatOllama

# Response cache — persists across restarts
set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# LLM with warm KV cache
llm = ChatOllama(
    model="llama3.2",
    keep_alive="30m"
)
```

This gives both caching layers with no additional infrastructure.

### Notes

- Response caching is **exact match by default** — even minor prompt differences cause cache misses. Use `RedisSemanticCache` if prompts vary but semantics are stable.
- KV cache warmth is **session-scoped** — it does not persist across Ollama restarts.
- Neither layer requires changes to LangGraph graph definitions or node implementations.
- For deployments handling sensitive data, confirm the SQLite cache file is stored in an encrypted volume or swap for an in-memory cache to avoid persisting PII.

---

## REQ-002: Tech Stack Analysis Workflow

### Overview

A workflow that runs `/tech-stack` (or equivalent analysis) against a connected repository, persists the results, and surfaces them in the Lintel UI.

### Requirements

1. **Workflow: `analyze-tech-stack`**
   - Triggered manually from the UI or via Slack command on a connected repo
   - Clones/pulls the target repository into a sandbox
   - Runs static analysis to detect: languages, frameworks, package managers, dependency versions, build tools, CI/CD configuration, infrastructure-as-code, test frameworks
   - Produces a structured tech-stack manifest (YAML/JSON) following the schema in `docs/tech-stack/*.yaml`

2. **Persistence**
   - Store tech-stack snapshots as events (`TechStackAnalyzed`) in the event store
   - Each snapshot is timestamped and linked to a repo + commit SHA
   - Support diffing between snapshots to detect stack drift over time

3. **UI**
   - Dedicated "Tech Stack" view per repository showing:
     - Current stack summary (languages, frameworks, versions)
     - Dependency health (outdated packages, known vulnerabilities)
     - Historical changes / drift timeline
     - Comparison across repositories in a workspace

4. **Scheduling**
   - Option to run on a schedule (e.g. weekly) or triggered by webhook on dependency file changes (`package.json`, `pyproject.toml`, `go.mod`, etc.)

---

## REQ-003: Repository Commit Tracking & Commit-Triggered Workflows

### Overview

Track commits from connected repositories, display them in the UI, and optionally trigger workflows based on commit activity.

### Requirements

1. **Commit ingestion**
   - Poll or receive webhooks for new commits on configured branches
   - Store commit metadata as events: SHA, author, message, timestamp, changed files, diff stats
   - Link commits to existing pipelines/work items when commit messages reference them

2. **UI — Commit feed**
   - Per-repository commit timeline view
   - Filter by branch, author, date range, file path
   - Show commit details: message, diff stats, linked pipelines
   - Activity heatmap (contributions over time)

3. **Commit-triggered workflows**
   - Configurable rules: "when a commit lands on `main` touching `src/lintel/api/**`, run the `review-changes` workflow"
   - Rule definition: branch pattern, file glob, author filter, workflow to trigger
   - Support cron-based scheduled triggers (e.g. "every Friday, run `weekly-review` on all commits since last run")

4. **Integration points**
   - GitHub/GitLab webhooks for real-time ingestion
   - Fallback: periodic `git fetch` + `git log` polling from sandbox

---

## REQ-004: Domain Model & Entity Extraction Workflow

### Overview

A workflow that analyses one or more repositories to extract domain models, entities, value objects, aggregates, and business processes — producing a living domain map.

### Requirements

1. **Workflow: `extract-domain-model`**
   - Accepts one or more repository references (supports cross-repo analysis)
   - Uses LLM-assisted code analysis to identify:
     - **Entities & aggregates** — classes/types that represent core business objects
     - **Value objects** — immutable types representing domain concepts
     - **Domain events** — events that capture state transitions
     - **Commands** — intent objects that trigger domain behaviour
     - **Business processes** — sequences of operations / state machines / sagas
     - **Bounded contexts** — logical boundaries between subdomains
   - Produces a structured domain model document (Markdown + structured data)

2. **Cross-repo analysis**
   - When multiple repos are provided, identify shared entities and cross-boundary interactions
   - Map which services own which aggregates
   - Detect entity duplication or inconsistency across services

3. **Persistence & UI**
   - Store as versioned domain model snapshots
   - UI view: entity relationship diagram (auto-generated), entity catalogue, process flow diagrams
   - Diff between versions to track domain evolution

4. **Re-run triggers**
   - Manual trigger or scheduled (e.g. after significant code changes detected by REQ-003)

---

## REQ-005: Integration Pattern Extraction Workflow

### Overview

A workflow that scans repositories to identify and document integration patterns — how services communicate, what protocols they use, and where coupling exists.

### Requirements

1. **Workflow: `extract-integration-patterns`**
   - Analyses codebase(s) to detect:
     - **Synchronous integrations** — REST/gRPC/GraphQL clients and servers, endpoint definitions
     - **Asynchronous integrations** — message queues (Kafka, RabbitMQ, NATS), event buses, pub/sub patterns
     - **Database integrations** — shared databases, read replicas, cross-service queries
     - **File/blob integrations** — S3, shared filesystems
     - **External API calls** — third-party service integrations (Stripe, Twilio, etc.)
   - For each integration, capture: source service, target service/API, protocol, data format, error handling strategy, retry/circuit breaker patterns

2. **Output**
   - Integration map (service dependency graph)
   - Pattern catalogue: which integration patterns are used and where
   - Anti-pattern detection: tight coupling, synchronous chains, missing error handling, no retries on external calls

3. **UI**
   - Service dependency graph visualization
   - Integration catalogue with filtering by pattern type, service, protocol
   - Coupling score per service

---

## REQ-006: Codebase Review & Improvement Workflow

### Overview

A workflow that reviews completed work (recent commits, PRs, or pipeline outputs), ranks code quality, provides feedback, and optionally applies improvements.

### Requirements

1. **Workflow: `review-and-improve`**
   - Inputs: commit range, PR reference, or "all changes since last review"
   - Review dimensions:
     - **Correctness** — logic errors, edge cases, off-by-one, null handling
     - **Security** — OWASP top 10, secrets in code, injection risks
     - **Performance** — N+1 queries, unnecessary allocations, missing indexes
     - **Maintainability** — complexity, naming, duplication, test coverage
     - **Architecture adherence** — does the code follow established patterns and boundaries?
   - Produces a structured review report with per-file scores and actionable findings

2. **Improvement mode**
   - After review, optionally generate improvement PRs for findings above a severity threshold
   - Each improvement is a separate commit with clear explanation
   - Requires approval gate before merging (uses existing approval flow)

3. **Ranking & trending**
   - Track review scores over time per repository / per contributor
   - Surface trends in the UI: "code quality improved 15% this month"
   - Identify recurring issues to suggest team-wide improvements

---

## REQ-007: Incident & Error Capture

### Overview

Integrate with error tracking platforms (Datadog, Sentry) to capture incidents and errors, link them to code changes, and optionally trigger remediation workflows.

### Requirements

1. **Ingestion**
   - Webhook receivers for Datadog alerts and Sentry error events
   - Capture: error type, stack trace, affected service, severity, first/last seen, occurrence count, affected users
   - Store as `IncidentDetected` events in the event store

2. **Correlation**
   - Link incidents to recent deployments / commits (by timestamp and service)
   - Link to relevant code files and lines (from stack traces)
   - Identify if a recent PR or pipeline run introduced the regression

3. **Automated response**
   - Configurable rules: "on P1 Sentry error in `lintel-api`, trigger `investigate-incident` workflow"
   - Investigation workflow: pull stack trace, find related code, check recent changes, produce root cause analysis
   - Optional: auto-create a work item / Slack thread for the incident

4. **UI**
   - Incident timeline per repository/service
   - Incident-to-commit correlation view
   - MTTR (mean time to resolution) tracking

---

## REQ-008: Team & Contributor Analytics

### Overview

Understand team dynamics, individual contributions, and provide feedback on work patterns — not as a surveillance tool but as a team health and collaboration improvement mechanism.

### Requirements

1. **Contributor tracking**
   - Aggregate per-contributor: commits, PRs, reviews given/received, pipeline runs triggered, incidents resolved
   - Track collaboration patterns: who reviews whom, pairing frequency, knowledge silos
   - Code ownership mapping: who knows what parts of the codebase best

2. **Team health metrics**
   - PR cycle time (open to merge)
   - Review turnaround time
   - Bus factor per module (how many people can maintain it)
   - Knowledge distribution score

3. **Feedback & insights**
   - Weekly/monthly team digest: key contributions, bottlenecks, suggestions
   - Individual contributor summaries (opt-in, private by default)
   - Identify overloaded contributors or unbalanced review load

4. **Privacy & ethics**
   - All individual metrics are private by default — only aggregate team metrics are visible to the team
   - Individual contributors can opt in to share their metrics
   - No tracking of hours, keystrokes, or activity timing — focus on outcomes not activity

---

## REQ-009: Team, Project & User Integration

### Overview

First-class modelling of teams, projects, and users within Lintel to support multi-team, multi-project workflows and permissions.

### Requirements

1. **Data model**
   - **User** — identity linked to Slack, GitHub, email; preferences, notification settings
   - **Team** — group of users; owns repositories and projects; has roles (admin, member, viewer)
   - **Project** — logical grouping of repositories, pipelines, and workflows; belongs to a team
   - **Workspace** — top-level tenant containing teams and projects

2. **Integration points**
   - Auto-sync team membership from Slack workspace / GitHub org
   - Map GitHub usernames to Slack users for cross-platform attribution
   - Project-scoped pipeline configuration: which workflows are enabled, what triggers are active

3. **Permissions & access control**
   - Role-based access: workspace admin, team admin, team member, viewer
   - Project-level permissions: who can trigger workflows, approve gates, view results
   - Audit log of permission changes

4. **UI**
   - Team management page: members, roles, connected repos
   - Project dashboard: repos, active pipelines, recent activity
   - User profile: connected accounts, preferences, activity summary

---

## REQ-010: Artifacts, Tests & Coverage Tracking

### Overview

Track build artifacts, test results, and code coverage as first-class entities linked to pipelines and commits.

### Requirements

1. **Test result ingestion**
   - Parse test output from pipeline runs (pytest, jest, go test, etc.)
   - Store per-test results: name, status (pass/fail/skip), duration, error message
   - Support standard formats: JUnit XML, pytest JSON, TAP

2. **Coverage tracking**
   - Ingest coverage reports (lcov, coverage.py JSON, Istanbul)
   - Store per-file and aggregate coverage percentages
   - Track coverage trends over time
   - Diff coverage: what coverage was added/removed by a specific PR

3. **Artifact management**
   - Store build artifacts (binaries, Docker images, reports) with metadata
   - Link artifacts to the pipeline run and commit that produced them
   - Retention policies: auto-expire artifacts after N days, keep release artifacts indefinitely

4. **UI**
   - Test results view per pipeline run: pass/fail breakdown, flaky test detection, duration trends
   - Coverage dashboard: per-repo trends, per-file heatmap, coverage gates (e.g. "block merge if coverage drops below 80%")
   - Artifact browser: download, inspect, compare across runs

5. **Quality gates**
   - Configurable rules: "fail pipeline if any test fails", "warn if coverage drops > 2%", "block merge if no tests added for new files"
   - Integrated with approval gate workflow

---

## REQ-011: Architecture Decision Records (ADR) Workflow

### Overview

Capture, manage, and surface Architecture Decision Records — the "why" behind technical choices — as a workflow-integrated process.

### Requirements

1. **Workflow: `create-adr`**
   - Triggered from: Slack thread discussion, PR review, manual request
   - Inputs: context (what prompted the decision), decision options considered, chosen option, consequences
   - LLM-assisted drafting: given a discussion thread or PR, extract the key decision and draft an ADR
   - Output: Markdown ADR following a standard template (title, status, context, decision, consequences)

2. **ADR management**
   - Store ADRs as versioned documents linked to repos and projects
   - Standard statuses: proposed, accepted, deprecated, superseded
   - Link ADRs to the code they affect (file paths, modules)
   - Cross-reference: ADRs can supersede or relate to other ADRs

3. **Auto-detection**
   - When a PR introduces a significant architectural change (new dependency, new pattern, structural refactor), suggest creating an ADR
   - Use domain model (REQ-004) and integration pattern (REQ-005) diffs to detect architectural shifts

4. **UI**
   - ADR catalogue per project: searchable, filterable by status/date/author
   - Timeline view: architectural evolution over time
   - ADR detail view: full document, linked code, related ADRs, discussion thread

5. **Persistence**
   - Store ADRs both as files in the repository (`docs/adr/`) and as events in Lintel
   - Sync: changes to ADR files in the repo are reflected in Lintel and vice versa

---

## REQ-012: Workflow Hooks & Event-Driven Triggers

### Overview

A hook system within Lintel that allows workflows to trigger other workflows when specific events occur — enabling composable, reactive automation pipelines.

### Requirements

1. **Hook definition**
   - A hook binds an **event pattern** to a **workflow trigger**
   - Event patterns: glob-style matching on event types (e.g. `pipeline.stage.completed`, `incident.detected`, `adr.created`, `commit.pushed`)
   - Workflow trigger: which workflow to start, with what parameters derived from the event payload
   - Conditions: optional filter expressions (e.g. "only if `severity == 'P1'`", "only if `branch == 'main'`")

2. **Hook types**
   - **Pre-hooks** — run before an action completes (can block/modify, e.g. validation gates)
   - **Post-hooks** — run after an event occurs (fire-and-forget or await completion)
   - **Scheduled hooks** — cron-based triggers that query for conditions and fire workflows

3. **Configuration**
   - Hooks defined per-project or per-workspace
   - Configuration via UI, API, or declarative YAML in the repository (`.lintel/hooks.yaml`)
   - Example:

   ```yaml
   hooks:
     - name: review-on-merge
       event: commit.pushed
       conditions:
         branch: main
       trigger:
         workflow: review-and-improve
         params:
           commit_range: "{{ event.before }}..{{ event.after }}"

     - name: adr-on-architecture-change
       event: pipeline.stage.completed
       conditions:
         stage: extract-domain-model
         result.architecture_changed: true
       trigger:
         workflow: create-adr
         params:
           context: "{{ event.result.changes_summary }}"

     - name: incident-response
       event: incident.detected
       conditions:
         severity: P1
       trigger:
         workflow: investigate-incident
         params:
           incident_id: "{{ event.incident_id }}"
   ```

4. **Execution**
   - Hook evaluation is event-driven — subscribe to the internal event stream
   - Hooks execute asynchronously by default (post-hooks)
   - Pre-hooks execute synchronously and can return `allow` / `deny` / `modify`
   - Circuit breaker: prevent infinite hook loops (A triggers B triggers A)
   - Max chain depth configurable (default: 5)

5. **Observability**
   - Log all hook evaluations: matched/skipped/failed
   - UI: hook execution history, chain visualization
   - Alert on hook failures or loop detection

6. **Built-in events** (emitted by Lintel core)
   - `pipeline.created`, `pipeline.stage.started`, `pipeline.stage.completed`, `pipeline.completed`
   - `commit.pushed`, `pr.opened`, `pr.merged`
   - `incident.detected`, `incident.resolved`
   - `adr.created`, `adr.status_changed`
   - `tech_stack.analyzed`, `domain_model.extracted`
   - `review.completed`, `approval.granted`, `approval.denied`
   - `work_item.created`, `work_item.completed`

---

## REQ-013: Editable Research & Plan Reports

### Overview

Allow users to edit the research report and plan report produced by workflows — turning AI-generated outputs into collaborative documents that can be refined before execution proceeds.

### Context

The `feature-to-pr` workflow (and similar workflows) produce two key intermediate artifacts:
1. **Research report** — codebase context, relevant files, patterns, and constraints discovered during the research stage
2. **Plan report** — step-by-step implementation plan with file changes, test strategy, and acceptance criteria

Currently these are read-only outputs. Users should be able to edit them to correct inaccuracies, add context the AI missed, adjust scope, or refine the approach before the workflow continues.

### Requirements

1. **Editable report UI**
   - Research and plan reports render as rich Markdown in the pipeline detail view
   - An "Edit" button switches the report into an inline editor (Markdown textarea or structured editor)
   - Support for both full-document editing and section-level editing (expand/collapse sections, edit individually)
   - Show diff between original AI-generated version and user-edited version

2. **Edit lifecycle**
   - Editing pauses the workflow at an implicit gate (similar to approval gate) — downstream stages do not proceed until the user confirms the report
   - Users can: **Accept as-is**, **Edit & confirm**, or **Regenerate** (re-run the stage with optional additional instructions)
   - On "Regenerate", the user can provide a text prompt to guide the AI (e.g. "also consider the auth module", "reduce scope to just the API layer")

3. **Versioning**
   - Every edit creates a new version of the report stored as an event (`ResearchReportEdited`, `PlanReportEdited`)
   - Version history is viewable in the UI — who edited, when, what changed
   - The workflow engine uses the latest confirmed version as input to subsequent stages

4. **API**
   - `PATCH /pipelines/{id}/stages/{stage_id}/report` — submit an edited report
   - `POST /pipelines/{id}/stages/{stage_id}/regenerate` — re-run the stage with optional guidance
   - `GET /pipelines/{id}/stages/{stage_id}/report/versions` — list report versions
   - Report content is stored as part of the stage output in the event store

5. **Workflow integration**
   - The `research` and `plan` nodes in the workflow graph emit a `report_ready` event and transition to a `waiting_for_confirmation` state
   - On confirmation (with or without edits), the node completes and passes the final report to downstream nodes
   - If the user edits the plan, the implementation stage receives the edited plan — not the original
   - Configurable per-workflow: which stages require confirmation vs auto-proceed (default: both research and plan require confirmation)

6. **Collaboration**
   - Multiple users can view the report simultaneously
   - Last-write-wins for edits (no real-time collaborative editing in v1)
   - Edit attribution: track which user made which edits
   - Slack notification when a report is ready for review/editing

---

## REQ-014: Sandbox Firewall & Resource Isolation

### Overview

Fine-grained runtime control over sandbox network access and filesystem permissions — allowing operators to restrict what a sandbox can reach and what it can modify, configurable per-sandbox and changeable at runtime.

### Context

Sandboxes currently use coarse-grained isolation: `network_mode: "none"` or `"bridge"`, `cap_drop: ["ALL"]`, and tmpfs mounts. This is insufficient for workflows that need partial network access (e.g. allow PyPI but block everything else) or selective filesystem restrictions (e.g. read-only source tree with writable output directory).

### Docker Capabilities Available

The following Docker primitives are available for implementation:

#### Network isolation
- **Custom bridge networks** — create per-sandbox or per-policy networks via `client.networks.create()` with internal/driver options
- **Runtime connect/disconnect** — `Network.connect(container)` and `Network.disconnect(container)` allow dynamic network attachment without container restart
- **Network modes** — `none`, `bridge`, `host`, `container:<id>` set at creation
- **DNS control** — custom DNS servers via `dns` parameter to restrict resolution
- **Docker network policies (2025)** — domain-based HTTP/HTTPS filtering with wildcard support (`*.pypi.org`, `github.com:443`); currently CLI-only, no SDK API yet

#### Filesystem isolation
- **Read-only root filesystem** — `read_only=True` at container creation
- **Selective mounts** — `volumes` with `mode='ro'` or `mode='rw'` per bind mount
- **tmpfs** — ephemeral writable directories with size limits (`tmpfs={'/tmp': 'size=100m'}`)
- **Seccomp profiles** — custom JSON profiles passed via `security_opt=['seccomp=/path/to/profile.json']` to restrict syscalls
- **AppArmor profiles** — MAC enforcement via `security_opt=['apparmor=profile-name']`
- **Capability control** — `cap_drop=['ALL']` + selective `cap_add` for least-privilege

#### Limitations
- No runtime filesystem permission changes post-creation (requires container recreation)
- Docker network policies (domain filtering) have no Python SDK support yet — CLI only
- Seccomp profiles must be file paths, not inline JSON

### Requirements

1. **Network firewall policies**
   - Define named network policies: `unrestricted`, `package-registries-only`, `no-network`, `custom`
   - `package-registries-only` allows: `pypi.org`, `registry.npmjs.org`, `proxy.golang.org`, `rubygems.org` (configurable allowlist)
   - `custom` accepts a list of allowed domains/IPs with optional port restrictions
   - Policies are assignable per-sandbox at creation or changed at runtime
   - Implementation: custom bridge networks with iptables rules for IP-based filtering; DNS-based filtering for domain allowlists (custom DNS proxy or dnsmasq in sidecar container)

2. **Filesystem access policies**
   - Define mount profiles: which host paths can be mounted, read-only vs read-write
   - Support read-only source tree with writable output directory pattern: `/workspace/src` (ro) + `/workspace/output` (rw)
   - Configurable tmpfs sizes per directory
   - Seccomp profile selection: `default`, `strict` (minimal syscalls), `custom` (user-provided JSON)
   - AppArmor profile support for environments where AppArmor is available

3. **Runtime control API**
   - `POST /sandboxes/{id}/network-policy` — change network policy at runtime (connect/disconnect networks)
   - `GET /sandboxes/{id}/network-policy` — get current network policy and connectivity status
   - `POST /sandboxes/{id}/cleanup-workspace` — clear workspace files (already implemented)
   - Network changes are immediate — no container restart required

4. **UI**
   - Network policy selector on sandbox creation (dropdown: unrestricted, package-registries-only, no-network, custom)
   - Runtime network toggle on sandbox detail page (with confirmation for escalating access)
   - Visual indicator of current network policy (badge showing active policy)
   - Filesystem policy display in sandbox configuration tab

5. **Workflow integration**
   - Workflows can specify required network policy per stage (e.g. `research` stage needs network, `code` stage does not)
   - Automatic policy transitions: network enabled for clone → disabled for code execution → enabled for push
   - Policy violations emit events (`SandboxPolicyViolation`) for audit

6. **Audit & observability**
   - Log all network policy changes as events (`SandboxNetworkPolicyChanged`)
   - Track network usage per sandbox (bytes in/out, DNS queries, blocked requests)
   - Alert on unexpected network access attempts from no-network sandboxes

### Implementation notes

- Phase 1: Named network policies using custom bridge networks + DNS control (fully supported by Docker SDK)
- Phase 2: Domain-based filtering via DNS proxy sidecar (dnsmasq or CoreDNS with policy plugin)
- Phase 3: Docker network policies integration when SDK support lands
- Filesystem policies are creation-time only — changing filesystem isolation requires sandbox recreation

---

## REQ-015: Internal Task Board

### Overview

A built-in task management board within Lintel that provides a flexible, configurable view of work items — similar to Jira or Notion boards. External integrations (Jira, Linear) mirror their data into this same internal model, giving teams a single place to see all work regardless of origin.

### Data Model

The task board extends the existing `WorkItem` with flexible metadata rather than introducing a separate entity.

#### Board

```python
@dataclass(frozen=True)
class Board:
    board_id: str
    project_id: str
    name: str
    columns: tuple[BoardColumn, ...]     # ordered columns (e.g. To Do, In Progress, Done)
    group_by: str = ""                   # tag key to group by (e.g. "epic", "team", "priority")
    default_sort: str = "created_at"     # field or tag key to sort within columns
    filters: dict[str, object] = field(default_factory=dict)  # saved filters

@dataclass(frozen=True)
class BoardColumn:
    column_id: str
    name: str                            # display name (e.g. "To Do", "In Review")
    maps_to_status: str                  # WorkItemStatus value this column represents
    wip_limit: int = 0                   # 0 = unlimited
    color: str = ""                      # optional hex color for the column header
```

#### Tags (flexible key-value metadata on WorkItem)

```python
@dataclass(frozen=True)
class Tag:
    key: str       # e.g. "epic", "priority", "component", "sprint"
    value: str     # e.g. "Auth Overhaul", "P1", "api", "2026-W10"
    color: str = ""
```

`WorkItem` gains:
- `tags: tuple[Tag, ...] = ()` — arbitrary key-value tags
- `column_position: int = 0` — ordering within a board column
- `external_ticket_id: str = ""` — (already planned in ENT-M2)
- `external_ticket_url: str = ""` — (already planned in ENT-M2)

Tags are fully user-defined — Lintel does not enforce a fixed set of keys. Common conventions (epic, priority, component, sprint) are suggested but not required.

### Requirements

1. **Board configuration**
   - Each project has one or more boards (e.g. "Engineering Board", "Design Board")
   - Columns are user-defined and map to `WorkItemStatus` values (many columns can map to the same status)
   - Column order is drag-and-drop reorderable in the UI
   - WIP limits: optional per-column limit that shows a visual warning when exceeded

2. **Tags & grouping**
   - Work items can have any number of tags (key-value pairs)
   - Tags are project-scoped — available tags are discovered from usage, not pre-defined
   - Group-by: board can group rows by any tag key (e.g. group by "epic" shows one swimlane per epic)
   - Filter: filter board by tag values, status, assignee, work type, date range
   - Bulk tag operations: select multiple items, add/remove tags

3. **Board views**
   - **Kanban view** — columns as vertical lanes, cards as work items, drag to move between columns
   - **List view** — table with sortable/filterable columns (like Notion database view)
   - **Grouped view** — list or kanban grouped by a tag key (swimlanes)
   - Users can switch between views; each view preserves its own sort/filter state

4. **Integration mirroring**
   - External ticketing integrations (Jira, Linear) sync into the same `WorkItem` + `Tag` model
   - External fields map to tags: Jira epic → `tag(key="epic", value="EPIC-123: Auth")`, Jira labels → tags, Jira priority → `tag(key="priority", value="High")`
   - Sync is bidirectional: moving a card on the Lintel board updates the external ticket status, and vice versa
   - Conflict resolution: last-write-wins with `external_synced_at` timestamp tracking
   - Items created in Lintel can optionally be pushed to the external tracker

5. **API**
   - `POST /projects/{id}/boards` — create a board
   - `GET /projects/{id}/boards` — list boards for a project
   - `GET /boards/{id}` — get board with columns and work items
   - `PATCH /boards/{id}` — update board config (columns, group_by, filters)
   - `PATCH /work-items/{id}/tags` — add/remove tags on a work item
   - `PATCH /work-items/{id}/position` — move item to a column + position (drag-and-drop)
   - `GET /projects/{id}/tags` — list all tag keys and values in use (for autocomplete)

6. **Events**
   - `BoardCreated`, `BoardUpdated` — board configuration changes
   - `WorkItemTagged`, `WorkItemUntagged` — tag changes
   - `WorkItemMoved` — column/position changes on the board
   - `ExternalTicketMirrored` — item synced from external tracker

7. **UI**
   - Board page accessible from the project sidebar
   - Kanban board with drag-and-drop (columns, card ordering)
   - Card displays: title, status badge, tags as colored chips, assignee avatar, work type icon
   - Quick-add: create a work item directly from the board (inline form at top of column)
   - Tag management: click a tag chip to filter by it, right-click for edit/remove
   - Epic swimlanes: when grouped by epic, collapsible rows with item count and progress bar

### Non-goals (v1)

- Custom fields beyond tags (no typed fields like number, date, dropdown — tags are string key-value only)
- Automations / rules (e.g. "when moved to Done, close the ticket") — use REQ-012 hooks for this
- Time tracking or story points
- Sub-tasks or parent-child relationships between work items
- Real-time collaborative editing of work item descriptions

---

## REQ-016: Agent Performance Tracking

### Overview

Track per-agent output quality, task completion rates, error rates, and human override frequency. Automated grading using an LLM-as-judge pattern scores each agent per cycle. Store `AgentPerformanceReviewed` events with grades, reasoning, and flagged issues. Provides the data foundation for the Chief of Staff agent and feedback loops.

### Requirements

1. **Metrics collection** — instrument each agent node in LangGraph workflows to emit performance events (latency, token usage, output quality signals, human overrides)
2. **Grading system** — LLM-as-judge evaluates agent outputs against acceptance criteria; produces a letter grade (A–F) with reasoning
3. **Event store integration** — `AgentPerformanceReviewed` events with: agent_id, cycle (weekly), grade, reasoning, flagged_issues, metrics snapshot
4. **Performance projections** — read-side projection aggregating trends per agent over time (grade history, improvement/regression detection)
5. **API** — `GET /agents/{id}/performance` (history), `GET /agents/performance/summary` (latest cycle for all agents)

---

## REQ-017: Human-in-the-Loop Approval Gates

### Overview

Replace auto-approve with real approval workflows in LangGraph. Agents flag uncertainty and route decisions to humans via Slack. Human corrections are captured as training signal for the Chief of Staff agent. Escalation routing when confidence is low.

### Requirements

1. **Approval nodes** — LangGraph interrupt-based nodes that pause workflow execution and notify a human via Slack DM or channel thread
2. **Approval UI** — approve/reject/comment from Slack (reactions or slash commands) and from the web UI
3. **Escalation** — configurable timeout; if no response within SLA, escalate to next reviewer or auto-approve with warning
4. **Correction capture** — when a human overrides an agent decision, store the original output, human correction, and reasoning as an `AgentCorrected` event
5. **Confidence threshold** — agents can set a confidence score; below threshold triggers automatic approval request

---

## REQ-018: Human Worker Nodes

### Overview

A "human agent" node type in LangGraph workflows that routes tasks to real people. Enables mixed human+AI agent teams where some work is done by agents and some by humans, all within the same workflow.

### Requirements

1. **Human node type** — a LangGraph node that pauses execution and assigns work to a person (by role, team, or specific user)
2. **Task assignment** — notification via Slack DM or work item assignment on the task board
3. **SLA tracking** — configurable deadline per human node; timeout triggers escalation or reassignment
4. **Result ingestion** — human submits output (text, code, file, approval) which feeds back into the workflow state like any agent output
5. **Handoff context** — human receives full context: what the workflow has done so far, what's expected, acceptance criteria
6. **Events** — `HumanTaskAssigned`, `HumanTaskCompleted`, `HumanTaskEscalated`

---

## REQ-019: Per-Agent Prompt & Memory Store

### Overview

Versioned, mutable prompt and memory store for each agent. The Chief of Staff agent can rewrite prompts, update memory, and adjust parameters. Every change is event-sourced for full auditability and A/B comparison.

### Requirements

1. **Prompt store** — each agent has a versioned system prompt; changes create new versions with diff tracking
2. **Agent memory** — per-agent persistent context (guidelines, preferences, learned patterns) that the agent reads at invocation
3. **Adjustable parameters** — per-agent config: creativity (temperature), risk tolerance, autonomy level, focus areas
4. **API** — `GET/PUT /agents/{id}/prompt`, `GET/PUT /agents/{id}/memory`, `GET/PUT /agents/{id}/config`
5. **Events** — `AgentPromptUpdated`, `AgentMemoryUpdated`, `AgentConfigUpdated` with before/after snapshots
6. **Rollback** — revert to any previous prompt/memory/config version

---

## REQ-020: Chief of Staff Agent

### Overview

A meta-agent that aggregates performance data across all agents, generates periodic review reports, presents them to the human lead, takes feedback, and translates it into prompt/memory/priority changes for individual agents. The orchestrator that closes the management loop.

### Requirements

1. **Performance aggregation** — reads from Agent Performance Tracking (REQ-016) projections to build a team-wide report
2. **Report generation** — weekly report with per-agent grade, trends, flagged issues, and recommendations
3. **Human review** — delivers report via Slack thread or UI; collects feedback (free text + structured approve/reject per recommendation)
4. **Feedback execution** — translates human feedback into concrete changes: rewrite prompts (REQ-019), update memory, adjust priorities, modify workflow assignments
5. **Agent communication** — notifies affected agents of changes (updated prompt/memory is picked up on next invocation)
6. **Autonomy rules** — high-performing agents get less intervention; low-performing agents get more oversight (configurable thresholds)
7. **Events** — `PerformanceReportGenerated`, `FeedbackReceived`, `AgentAdjustmentApplied`

---

## REQ-021: Feedback Loop & Self-Improvement

### Overview

Closed feedback loop ensuring that agent adjustments made by the Chief of Staff actually improve performance. A/B tracking, before/after metrics, and automated weekly cycles.

### Requirements

1. **A/B tracking** — when a prompt/config change is applied, track performance before and after with statistical comparison
2. **Automated cycle** — cron-triggered weekly: collect metrics → generate report → notify human → apply feedback → measure impact
3. **Regression detection** — if an agent's grade drops after a change, flag it and suggest rollback
4. **Manual + automated signals** — human corrections (REQ-017), output quality scores (REQ-016), and task completion rates all feed into the loop
5. **Improvement log** — event-sourced history of all changes and their measured impact, viewable per agent

---

## REQ-022: Spec Workshop

### Overview

Collaborative workspace for defining and refining product specifications. Structured spec types provide a single source of truth for product intent, feeding downstream into Architecture Decisions and Work Items.

### Requirements

1. **Spec types** — Product Overview (strategic context), Feature Specs (individual capability definitions), Technical Constraints (cross-cutting: security, performance, integrations)
2. **AI agent assistance** — drafting from source material, quality checks (ambiguity, gaps, conflicts, duplication), suggesting feature splits/merges (human-confirmed)
3. **Versioning** — every edit creates a new version; diff comparison between versions; aggregate project-level comparison
4. **Source material integration** — agent can draft from Context Attachments (REQ-027): docs, images, transcripts, existing code
5. **Collaboration** — shared editing, comments, mentions; specs are living documents updated throughout the project lifecycle
6. **Downstream links** — specs link to Architecture Decisions (REQ-023) and Work Items; changes propagate alerts via Drift Detection (REQ-024)
7. **Import/export** — markdown import/export; PDF export
8. **Events** — `SpecCreated`, `SpecUpdated`, `SpecQualityChecked`, `SpecFeatureSplit`, `SpecFeatureMerged`

---

## REQ-023: Architecture Decisions

### Overview

Living architecture layer that captures engineering decisions as events. Foundations, diagrams, and per-feature technical plans linked bidirectionally to specs. Every change is tracked and auditable.

### Requirements

1. **Decision types** — Foundations (project-wide stack, principles, security, deployment), System Diagrams (Mermaid-based architecture and data flow), Feature Plans (per-feature: APIs, data models, UI behavior, testing)
2. **Template system** — configurable templates for consistent structure; project-level and org-level templates
3. **AI agent assistance** — drafting, reviewing for gaps/conflicts, generating Mermaid diagrams, detecting inconsistencies across decisions/code/specs
4. **Bidirectional linking** — Feature Plans link to Feature Specs (REQ-022); renaming propagates
5. **Codebase awareness** — agent references Codebase Index (REQ-026) when drafting plans; highlights specific files requiring changes
6. **Sync alerts** — flags when code changes invalidate decisions or spec updates aren't reflected; triggers guided human resolution
7. **Events** — `ArchitectureDecisionRecorded`, `ArchitectureDecisionUpdated`, `ArchitectureDriftDetected`

---

## REQ-024: Drift Detection

### Overview

Continuous sync engine across specs, architecture decisions, and code. Implemented as a projection over change events from all three layers. Detects when any layer diverges from the others and triggers human-in-the-loop resolution.

### Requirements

1. **Three-layer monitoring** — watches spec changes (REQ-022), architecture changes (REQ-023), and code changes (REQ-026) via event streams
2. **Drift types** — code invalidates architecture decision, spec update not reflected in technical plan, architecture conflicts with implementation, foundation drift from codebase
3. **Projection-based** — drift state is a read-side projection over spec/architecture/code change events (natural fit for event sourcing)
4. **Alerts** — surface in UI with severity level; Slack notifications for high-severity drift
5. **Guided resolution** — agent explains the drift, suggests remediation steps, human approves/modifies the fix
6. **Reindexing triggers** — code push webhooks trigger drift re-evaluation against current specs and architecture
7. **Events** — `DriftDetected`, `DriftResolved`, `DriftEscalated`

---

## REQ-025: Feedback Ingestion

### Overview

API endpoint to capture user and product feedback with technical context. AI categorizes and prioritizes feedback, auto-generates Work Items, and feeds into the Chief of Staff loop. Closes the loop from production usage back into the build process.

### Requirements

1. **Capture API** — lightweight endpoint accepting user feedback with optional technical context (browser, device, session, recent code changes)
2. **AI categorization** — classify as bug, feature request, performance issue, UX feedback; assign priority score
3. **Work Item generation** — auto-create Work Items with code context and suggested fixes; link to relevant specs/architecture decisions
4. **Slack alerts** — critical issues trigger immediate Slack notifications
5. **Inbox UI** — filterable dashboard showing all feedback with status, priority, and linked Work Items
6. **Spec feedback** — high-signal feedback can be routed to Spec Workshop (REQ-022) for requirement refinement
7. **Events** — `FeedbackReceived`, `FeedbackCategorized`, `FeedbackWorkItemCreated`

---

## REQ-026: Codebase Index

### Overview

Ingest, chunk, and embed entire codebases for semantic search and agent consumption. Git integration with webhook-triggered reindexing. Enables reverse-engineering specs from code, codebase-aware work item generation, and legacy migration support.

### Requirements

1. **Ingestion** — connect via Git (local or remote); read files from configured branch
2. **Chunking & embedding** — split code into semantic chunks; embed for vector search; background processing with progress tracking
3. **Webhook reindexing** — auto-reindex on push to monitored branch; incremental updates (only changed files)
4. **Agent skill** — exposed as a skill so all agents can semantically search and reference code during workflows
5. **Reverse engineering** — generate spec drafts and architecture decisions from existing code (legacy codebase onboarding)
6. **Migration support** — map legacy codebases for documentation and migration planning
7. **Drift layer** — feeds code change events into Drift Detection (REQ-024)
8. **Events** — `CodebaseConnected`, `CodebaseIndexed`, `CodebaseReindexed`

---

## REQ-027: Context Attachments

### Overview

File store for documents, images, audio, and other artifacts that provide context to agents. Attachable to threads, work items, specs, and architecture decisions. Embedded and searchable for agent retrieval.

### Requirements

1. **Upload** — API and UI upload for common file types (docs, images, audio, video, Office formats)
2. **Attachment points** — attach to threads, work items, specs (REQ-022), architecture decisions (REQ-023)
3. **Embedding & search** — file contents are embedded for semantic retrieval; agents dynamically pull relevant attachments during workflows
4. **Document linking** — inline links within specs/decisions that reference attachments for traceability
5. **Organization** — folder-based organization per project; descriptive naming conventions
6. **Events** — `AttachmentUploaded`, `AttachmentLinked`, `AttachmentRemoved`

---

## REQ-028: Workflow Templates

### Overview

Reusable LangGraph workflow patterns for common tasks. Define once, instantiate many times with different inputs. Reduces setup time for repetitive workflows and enables teams to share proven patterns.

### Requirements

1. **Template registry** — versioned collection of workflow templates with metadata (name, description, required inputs, expected outputs)
2. **Common templates** — ship with built-in templates: "review PR", "implement feature from spec", "migrate legacy module", "security audit", "code review", "research task"
3. **Custom templates** — teams can create, share, and customize templates from existing workflows
4. **Instantiation** — create a workflow run from a template with specific inputs; template defines the graph structure, user provides the context
5. **Versioning** — template changes create new versions; existing runs continue on the version they started with
6. **Events** — `WorkflowTemplateCreated`, `WorkflowTemplateUpdated`, `WorkflowFromTemplateStarted`

---

## REQ-029: Agent Trust Scores

### Overview

Graduated trust/autonomy system for agents based on behavioral tracking. Instead of binary human-in-the-loop, each agent has a dynamic trust score (0–1000) that determines how much oversight it needs. High performers earn autonomy; low performers get restrictions. The Chief of Staff agent (REQ-020) adjusts trust scores based on performance reviews.

### Requirements

1. **Trust score per agent** — dynamic 0–1000 score stored as an event-sourced projection over agent action outcomes
2. **Score adjustments** — successful task completion: +10; policy violation: up to -100; human override/correction: -20; configurable per action type
3. **Autonomy tiers** — score ranges determine oversight level:
   - **900+**: Full autonomy, no approval needed
   - **700–899**: Normal operation, periodic review
   - **500–699**: Limited actions, all actions logged with reasoning
   - **300–499**: Requires human approval before execution (REQ-017)
   - **0–299**: Suspended, cannot act autonomously
4. **Scope narrowing** — when trust drops, automatically restrict the agent's available tools and action types (not just oversight level)
5. **Human sponsor** — each agent has an assigned human sponsor who is accountable and receives escalations
6. **Trust recovery** — agents can regain trust through successful supervised execution; recovery rate is slower than degradation rate
7. **API** — `GET /agents/{id}/trust` (current score + history), `POST /agents/{id}/trust/adjust` (manual adjustment with reason)
8. **Events** — `AgentTrustScoreChanged`, `AgentScopeNarrowed`, `AgentScopeRestored`, `AgentSuspended`, `AgentReinstated`

---

## REQ-030: Agent Action Governance

### Overview

Deterministic policy-based control layer that intercepts every agent action and applies a three-state decision: ALLOW, DENY, or REQUIRE_APPROVAL. Implemented as LangGraph middleware wrapping all tool calls. Policies are declarative (YAML config) so the Chief of Staff agent can modify governance rules without code changes.

### Requirements

1. **Three-state decision model** — every agent tool call is evaluated and receives ALLOW, DENY, or REQUIRE_APPROVAL before execution
2. **Policy engine** — declarative YAML policies defining rules per agent role, action type, and context:
   - Allowed/denied tool categories per agent
   - Rate limiting per action type (e.g., max 60 LLM calls/hour)
   - Resource limits (token budgets, API call caps, time windows)
   - Domain restrictions (which repos, channels, or resources an agent can access)
3. **LangGraph middleware** — governance layer wraps every tool call in the workflow graph; transparent to agent logic
4. **Layered validation** — defense-in-depth with multiple checkpoint rules; a single DENY at any layer blocks the action
5. **Trust score integration** — policies reference the agent's trust score (REQ-029) to determine thresholds; lower trust = stricter policies
6. **CoS-modifiable** — Chief of Staff agent (REQ-020) can update governance policies as part of agent adjustments
7. **Audit logging** — every action decision is recorded with: timestamp, agent_id, action, arguments, decision (ALLOW/DENY/REQUIRE_APPROVAL), matching policy rule, trust score at time of decision
8. **Events** — `AgentActionAllowed`, `AgentActionDenied`, `AgentActionApprovalRequested`, `GovernancePolicyUpdated`

---

## REQ-031: Agent Prompt Evolution

### Overview

Automated prompt optimization system that measurably improves agent performance through structured evolution algorithms. When the Chief of Staff agent (REQ-020) or automated cycle (REQ-021) triggers a prompt change, the system applies optimization techniques and measures before/after performance against benchmarks. Applies prompt evolution algorithms with measurable outcomes.

### Requirements

1. **Prompt optimization algorithms** — support multiple evolution strategies:
   - **Gradient-based** — use LLM-generated feedback signals to iteratively refine prompts
   - **Structure evolution** — optimize not just prompt text but workflow graph topology
   - **Instruction refinement** — iterative improvement of instruction-following clarity
2. **Per-agent benchmarks** — each agent has a benchmark suite defining expected quality (test cases with expected outputs, quality rubrics, task-specific metrics)
3. **Before/after measurement** — every prompt change triggers a benchmark run; results are compared statistically to the previous version
4. **Rollback on regression** — if a prompt change degrades benchmark scores beyond a configurable threshold, automatically rollback and flag for human review
5. **Evolution history** — full event-sourced history of prompt versions, benchmark results, and optimization decisions
6. **Integration with REQ-019** — operates on the per-agent prompt store; each optimization produces a new prompt version
7. **Integration with REQ-021** — part of the automated feedback cycle; can be triggered by CoS agent or on schedule
8. **Events** — `PromptEvolutionStarted`, `PromptBenchmarkCompleted`, `PromptEvolutionAccepted`, `PromptEvolutionRolledBack`

---

## REQ-032: Per-Agent Model Selection

### Overview

Different agents should use different LLM models based on their task complexity, cost constraints, and performance needs. Simple classification tasks use cheaper/faster models; complex reasoning tasks use more capable models. Model selection is part of the agent config (REQ-019) and can be adjusted by the Chief of Staff agent.

### Requirements

1. **Per-agent model config** — each agent has a configured model (provider + model ID) in its config store (REQ-019)
2. **Model selection rationale** — config includes a reason field documenting why this model was chosen for this agent
3. **Cost-aware selection** — model config includes cost tier (low/medium/high) and token budget per invocation
4. **Runtime override** — environment variable overrides per agent for deployment flexibility (e.g., `LINTEL_PLANNER_MODEL=claude-sonnet-4-6`)
5. **Fallback chain** — ordered list of fallback models if primary is unavailable; enables graceful degradation
6. **Performance correlation** — track agent performance (REQ-016) alongside model used; surface when a model change improves/degrades quality
7. **CoS-adjustable** — Chief of Staff can recommend model changes as part of agent adjustments
8. **Events** — `AgentModelChanged`, `AgentModelFallbackUsed`

---

## REQ-033: Composable Agent Skills

### Overview

Reusable, versioned skill definitions that any agent can load at runtime. Skills are modular capability units (e.g., "code review", "sprint planning", "project estimation") defined as structured markdown with trigger conditions, methodology, and output templates. Keeps agent capabilities composable rather than monolithic.

### Requirements

1. **Skill definition format** — structured markdown with: metadata (name, version, author), trigger conditions (when to activate), methodology/framework, output template, examples
2. **Skill registry** — versioned collection of available skills; built-in skills ship with Lintel, custom skills can be added per project/org
3. **Dynamic loading** — agents load relevant skills at runtime based on task context; skills augment the agent's system prompt
4. **Auto-selection** — agents can auto-select applicable skills based on trigger conditions matching the current task, not just explicit invocation
5. **Cross-agent reuse** — same skill usable by multiple agents; e.g., "estimation" skill used by both planner and PM agents
6. **Skill composition** — multiple skills can be active simultaneously; skills don't conflict (isolated namespaces)
7. **Output standardization** — skills enforce consistent output formats; enables downstream processing and performance grading (REQ-016)
8. **Events** — `SkillLoaded`, `SkillExecuted`, `SkillRegistered`, `SkillUpdated`

---

## REQ-034: Agent-Utility Separation

### Overview

Enforce a clear boundary between agent nodes (where LLM reasoning adds value) and utility nodes (deterministic operations) in workflows. Not every step needs an agent. Performance tracking aggregation, drift detection scanning, event projection updates, and data normalization should be plain utility functions, not agent-wrapped code. This reduces cost, improves reliability, and makes the system honest about where AI is actually used.

### Requirements

1. **Node type classification** — every LangGraph node is explicitly classified as `agent` (requires LLM) or `utility` (deterministic logic)
2. **Utility nodes** — no LLM invocation; pure functions with predictable inputs/outputs; no token cost; no latency variance
3. **Agent nodes** — LLM-backed reasoning; subject to governance (REQ-030), trust scoring (REQ-029), and performance tracking (REQ-016)
4. **Workflow validation** — lint rule that flags agent nodes doing deterministic work (e.g., data normalization, HTTP fetching, deduplication)
5. **Cost attribution** — token costs are only attributed to agent nodes; utility nodes have zero LLM cost; enables accurate per-workflow cost tracking
6. **Graceful degradation** — when LLM APIs are unavailable, agent nodes can fall back to heuristic scoring (degraded mode) while utility nodes continue unaffected
7. **Documentation** — each workflow template (REQ-028) documents which nodes are agents vs utilities and why
