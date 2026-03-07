# Codebase Survey - api

## Survey Scope

**Tech Area:** api
**Task Context:** Investigate Concourse CI architecture to inform Lintel's pipeline/scheduling design — "Concourse for AI" with LangGraph pipelines, Slack channels, and single-node architecture.
**Survey Date:** 2026-03-07

## Architecture Overview

### Directory Structure

```
src/lintel/
  contracts/          # Pure domain contracts — types, commands, events, protocols
    types.py          # All domain value objects (frozen dataclasses)
    events.py         # All event types + EVENT_TYPE_MAP registry
    commands.py       # Command intent objects
    protocols.py      # Protocol interfaces (EventStore, ModelRouter, SandboxManager…)
  workflows/
    state.py          # LangGraph TypedDict state
    feature_to_pr.py  # The only compiled workflow graph (StateGraph)
    nodes/            # One async function per graph node
      ingest.py / route.py / plan.py / implement.py / review.py
  agents/
    runtime.py        # AgentRuntime: model call + event emission
  infrastructure/
    event_store/postgres.py     # PostgresEventStore (asyncpg)
    channels/slack/adapter.py   # SlackChannelAdapter
    models/router.py            # LiteLLM ModelRouter
    projections/engine.py       # InMemoryProjectionEngine
    projections/thread_status.py
    projections/task_backlog.py
    sandbox/                    # Docker sandbox (implementation stubs)
    vault/postgres_vault.py
    repos/github_provider.py, repository_store.py
    observability/tracing.py, metrics.py, correlation.py
  api/
    routes/           # FastAPI routers (~25 files)
    schemas/          # Pydantic request/response schemas
    deps.py           # FastAPI dependency injection
ui/src/
  features/workflows/
    pages/WorkflowEditorPage.tsx   # React Flow visual DAG editor
    components/nodes/              # AgentStepNode, ApprovalGateNode
```

## Key Patterns

### Pattern 1: Event-Sourced CQRS with Postgres
- All state changes recorded as immutable `EventEnvelope` subclasses appended to per-thread streams
- Optimistic concurrency via `stream_version`, SHA-256 hash chaining for tamper detection
- `stream_id` is `thread:{workspace}:{channel}:{ts}`
- 50+ event types in `events.py`

### Pattern 2: Protocol-Based Infrastructure Abstraction
- Every external dependency expressed as a `Protocol` interface in `contracts/protocols.py`
- 9 Protocol classes; ~12 infrastructure implementations
- Domain code imports only protocols, never infrastructure

### Pattern 3: LangGraph StateGraph Workflow
- Single compiled `StateGraph[ThreadWorkflowState]`: ingest → route → plan → approval_gate_spec → implement → review → approval_gate_merge → close
- Human-in-the-loop gates use `interrupt_before`
- Postgres checkpointing via `AsyncPostgresSaver`

### Pattern 4: Frozen Dataclass Commands and Events
- 13 commands express intent; 50+ events record past facts
- `EVENT_TYPE_MAP` maps string type names to classes for deserialization

### Pattern 5: In-Memory CQRS Read-Side Projections
- `InMemoryProjectionEngine` dispatches events to registered `Projection` implementations
- `ThreadStatusProjection` and `TaskBacklogProjection`; rebuilt from event store on demand

## Key Files

| File | Purpose | LOC | Relevance |
|------|---------|-----|-----------|
| `contracts/types.py` | All domain value objects: ThreadRef, WorkflowPhase, AgentRole, PipelineRun, Stage, WorkItem, SandboxJob, TriggerType | 527 | HIGH |
| `contracts/events.py` | 50+ event types and EVENT_TYPE_MAP registry | 425 | HIGH |
| `infrastructure/event_store/postgres.py` | Append-only Postgres event store with hash chaining | 215 | HIGH |
| `contracts/protocols.py` | 9 Protocol interfaces | 309 | HIGH |
| `workflows/feature_to_pr.py` | The only concrete workflow graph | 76 | HIGH |
| `agents/runtime.py` | AgentRuntime: model call + event emission | 121 | HIGH |
| `workflows/nodes/implement.py` | SandboxManager integration | 46 | HIGH |
| `ui/.../WorkflowEditorPage.tsx` | React Flow visual DAG editor | 270 | HIGH |

## Code Samples

### LangGraph Graph Construction
```python
# src/lintel/workflows/feature_to_pr.py:24-75
def build_feature_to_pr_graph() -> StateGraph[Any]:
    graph: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    graph.add_node("ingest", ingest_message)
    graph.add_node("route", route_intent)
    graph.add_node("plan", plan_work)
    graph.add_node("approval_gate_spec", lambda s: s)
    graph.add_node("implement", spawn_implementation)
    graph.add_node("review", review_output)
    graph.add_node("approval_gate_merge", lambda s: s)
    graph.add_node("close", lambda s: {**s, "current_phase": "closed"})
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "route")
    graph.add_conditional_edges("route", _route_decision, {"plan": "plan", "close": "close"})
    # ... edges omitted for brevity
    return graph
```

### Workflow State TypedDict
```python
# src/lintel/workflows/state.py:1-23
class ThreadWorkflowState(TypedDict):
    thread_ref: str
    correlation_id: str
    current_phase: str
    sanitized_messages: Annotated[list[str], add]
    intent: str
    plan: dict[str, Any]
    agent_outputs: Annotated[list[dict[str, Any]], add]
    pending_approvals: list[str]
    sandbox_id: str | None
    sandbox_results: Annotated[list[dict[str, Any]], add]
    pr_url: str
    error: str | None
```

## Integration Points

1. **Wire Command Bus to LangGraph Executor** — Routes build commands but don't dispatch them. Replace `return asdict(command)` with actual `graph.ainvoke()`.
2. **Pipeline Run Scheduler** — Add `SchedulePipelineRun` command + background service reading `TriggerFired` events.
3. **Stage Duration Tracking** — `Stage.duration_ms` field exists but not populated from event timestamps.
4. **SSE Streaming Endpoint** — No SSE endpoint exists. Add `GET /api/v1/runs/{run_id}/stream` using `StreamingResponse`.
5. **Compile Stored Visual Graph into LangGraph** — Visual editor saves `{ nodes, edges }` but nothing compiles them into executable graphs.

## Gaps and Opportunities

| Gap | Severity | Description |
|-----|----------|-------------|
| Routes are stubs | HIGH | Commands built but not dispatched |
| No streaming output | HIGH | nats-py declared but unused; no SSE endpoint |
| Single hardcoded workflow | HIGH | Visual editor saves graphs but can't execute them |
| Event endpoints are placeholders | MEDIUM | Return hardcoded empty lists |
| Workflow nodes are stubs | MEDIUM | Most return hardcoded data |
| In-memory projections | MEDIUM | Lost on restart |
| Metrics in app.state dicts | LOW | In-process, not queryable historically |

## Notes for Synthesis

**Strengths:** Domain model directly maps to Concourse concepts (Pipeline, Stage, Trigger, WorkItem, Approval). Event sourcing with hash chaining gives strong auditability. Protocol interfaces allow new scheduler components without touching domain code. Visual workflow editor exists.

**Weaknesses:** Commands not dispatched. One hardcoded workflow. No trigger scheduler. No streaming. In-memory projections lost on restart.

**Risk:** `ThreadRef` (workspace/channel/thread_ts) ties every pipeline run to a Slack thread. Concourse-style scheduled/webhook-triggered pipelines need an extended identifier scheme.
