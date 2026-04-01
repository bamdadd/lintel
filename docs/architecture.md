# Architecture

## Overview

Lintel is an event-sourced CQRS platform that orchestrates multi-agent workflows triggered from Slack threads.

## Core patterns

### Event sourcing

All state changes are recorded as immutable events in an append-only store. Events are past-tense facts that are never modified or deleted. The event store uses hash chaining for tamper evidence and idempotency keys for deduplication.

### CQRS

Commands express intent and may fail. Events record what happened. Read models (projections) are built by replaying events and maintained by subscribing to new events.

### Clean architecture

```
contracts/  →  Pure types, Protocol interfaces (no I/O)
domain/     →  Business logic (depends only on contracts)
api/        →  HTTP layer (FastAPI)
infrastructure/  →  Concrete implementations of Protocols
```

Domain code never imports from infrastructure. Service boundaries are defined by Protocol interfaces in `contracts/protocols.py`.

## Key abstractions

| Protocol | Responsibility |
|---|---|
| `EventStore` | Append-only event persistence |
| `Deidentifier` | PII detection and anonymization |
| `PIIVault` | Encrypted PII placeholder storage |
| `ChannelAdapter` | Messaging channel abstraction (Slack) |
| `ModelRouter` | LLM provider selection and invocation |
| `SandboxManager` | Isolated code execution containers |
| `RepoProvider` | Git and PR operations |
| `SkillRegistry` | Dynamic skill registration |

## Event flow

```
User message (Slack)
  → ChannelAdapter translates to canonical event
  → Deidentifier scans and anonymizes PII
  → EventStore persists ThreadMessageReceived
  → WorkflowEngine routes to LangGraph graph
  → Agents execute steps (plan, code, review)
  → SandboxManager runs code in isolation
  → RepoProvider creates branches and PRs
  → Human approves via Slack interactive components
  → EventStore records all decisions
```

## Thread lifecycle

Each Slack thread maps to a `ThreadRef(workspace_id, channel_id, thread_ts)` which serves as the canonical workflow instance identifier. The thread progresses through phases: `ingesting → planning → awaiting_spec_approval → implementing → reviewing → awaiting_merge_approval → merging → closed`.

## Domain sub-systems

### Metrics (`domain/metrics/`)

The metrics engine (`MetricsEngine`) aggregates four metric families: agent metrics (token usage, task completion, error rates), DORA metrics (deployment frequency, lead time, change failure rate, MTTR), human metrics (review turnaround, approval latency), and team metrics (throughput, velocity, collaboration scores). Each family has its own collector module; the engine provides a unified query interface.

### Workflow hooks (`domain/hooks/`)

`HookEngine` allows registering callbacks that fire at workflow lifecycle points (before/after node execution, on error, on completion). Hooks are matched via glob-style patterns against node names and workflow types. Used for audit trails, custom notifications, and guardrail enforcement.

### Notifications (`domain/notifications/`)

`NotificationDispatcher` delivers notifications across channels (Slack, email, webhook) based on configurable notification rules. Integrates with the event bus to react to domain events (stage completion, approval requests, pipeline failures).

### Reviews (`domain/reviews/`)

`ReviewEngine` orchestrates automated codebase reviews. Manages review models (findings, severity, suggestions) and coordinates between the reviewer agent and the review API surface.

### Guardrails (`domain/guardrails/`)

A condition language (`condition_lang.py`) for expressing guardrail rules evaluated by `GuardrailEvaluator`. Includes cost rules, escalation policies, and an `ApprovalBridge` that connects guardrail violations to the approval request workflow. Default rules are seeded from `seeds.py`.

### Authentication (`domain/auth/` + `auth-api/`)

Builtin JWT authentication. `domain/auth/` provides JWT token creation/validation and password hashing. `packages/auth-api/` exposes login routes and FastAPI middleware for request authentication.

### Git events (`domain/git_events.py`)

`GitEventListener` processes incoming git webhook events (push, PR opened/merged, branch created/deleted) and translates them into domain events that can trigger workflows or update project state.

### Workflow base class (`workflows/base.py`)

`WorkflowNode` is the abstract base class for all LangGraph workflow nodes, providing a standard interface for stage tracking, error handling, and config access.

### Approval gates (`workflows/nodes/approval_gate.py`)

`ApprovalGateNode` implements human-in-the-loop approval within workflow graphs using LangGraph interrupts. Pauses execution until an approval or rejection is received.

### Sandbox storage limits (`sandbox/`)

`StorageLimits` and `StorageUsage` types enforce per-sandbox disk quotas, preventing runaway file creation during code execution.

### Experiment run metrics (`experimentation-api/run_metrics.py`)

Extends the experimentation API with per-run metric tracking, allowing experiments to record and query time-series metric data.

## Security

- PII is detected and replaced with stable placeholders before reaching any LLM
- The PII vault encrypts raw values with Fernet; reveal requires human authorization
- Sandbox containers run with `--cap-drop ALL`, seccomp profiles, read-only root filesystem, and no network access
- All actions are auditable through the event store
