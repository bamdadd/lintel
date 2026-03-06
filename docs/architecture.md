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

## Security

- PII is detected and replaced with stable placeholders before reaching any LLM
- The PII vault encrypts raw values with Fernet; reveal requires human authorization
- Sandbox containers run with `--cap-drop ALL`, seccomp profiles, read-only root filesystem, and no network access
- All actions are auditable through the event store
