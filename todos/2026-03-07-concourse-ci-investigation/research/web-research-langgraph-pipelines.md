# Web Research - LangGraph Pipeline Model

## Executive Summary

LangGraph provides a low-level, code-first graph orchestration framework where workflows are `StateGraph` objects — directed graphs of Python functions connected by typed edges and shared state. Unlike Concourse's declarative YAML, LangGraph excels at non-deterministic AI workflows: conditional branching driven by LLM output, mid-execution human approval, persistent state across failures, and dynamic parallelism are first-class. Five streaming modes allow real-time token streaming. The `Send` API supports dynamic fan-out/fan-in. Per-node `RetryPolicy` provides configurable retries. LangSmith provides integrated observability with OTEL export.

## StateGraph Model

- `StateGraph` parameterized by TypedDict, dataclass, or Pydantic model
- Nodes are plain Python functions `(state, config) -> dict`; return dicts merged via reducers
- Normal edges: unconditional; conditional edges: routing function returns next node name(s)
- `Command` return type combines state update + goto directive
- Node caching via `CachePolicy(ttl=seconds)`
- Recursion limit defaults to 1000 super-steps

## State Management

- State fields are "channels" with optional reducer functions
- `Annotated[list[str], operator.add]` for safe parallel appending
- `add_messages` reducer: tracks message IDs for appends + targeted overwrites
- Without reducer: last-write-wins (dangerous for parallel branches)
- Context schema for non-persisted dependencies (LLM providers, DB connections)

## Checkpointing

- `StateSnapshot` saved after every super-step, keyed by `thread_id`
- Implementations: `InMemorySaver` (tests), `SqliteSaver` (dev), `AsyncPostgresSaver` (production)
- **Time travel**: pass `thread_id` + `checkpoint_id` to re-execute from any historical point
- `graph.update_state()`: directly modify state at any checkpoint
- Schema migrations: adding/removing keys is backward-compatible

## Human-in-the-Loop

- **Static breakpoints**: `graph.compile(interrupt_before=["node_name"])`
- **Dynamic `interrupt(payload)`**: call anywhere inside a node; resume via `Command(resume=value)`
- Payload surfaced in `__interrupt__` field; full state preserved indefinitely
- For Lintel: agent pauses at critical action → surfaces approval to Slack → waits for reply → resumes

## Subgraphs

- Any compiled `StateGraph` usable as a node in a parent graph
- Checkpointing, interrupts, state inspection propagate automatically
- Shared state keys: add directly; different schemas: wrap with translation function
- Stream from subgraphs with `subgraphs=True`

## Streaming (5 Modes)

| Mode | Description |
|------|-------------|
| `values` | Full state snapshot after each super-step |
| `updates` | Only changed channels per step |
| `messages` | Token-by-token LLM output with `langgraph_node` metadata |
| `custom` | Arbitrary data from nodes via `get_stream_writer()` |
| `debug` | Comprehensive execution trace |

- Multiple modes combinable: `stream_mode=["updates", "custom"]`
- `subgraphs=True` for nested subgraph events

## Parallel Execution

- **Static fan-out**: multiple edges from one node → destinations run concurrently in same super-step
- **Dynamic fan-out (`Send` API)**: routing function returns `[Send("worker", state_slice), ...]` for runtime-dynamic parallelism
- **Superstep atomicity**: parallel branches are transactional; if any fails, entire super-step fails
- Production: 70+ parallel nodes in single thread documented
- **Reducers mandatory for fan-in channels**

## Error Handling

- `RetryPolicy` per node: `max_attempts`, `initial_interval`, `backoff_factor`, `jitter`, `retry_on`
- After retries exhausted: error in checkpoint; graph stops unless fallback edges exist
- Multi-level: node (RetryPolicy), graph (conditional fallback routing), application (catch from invoke)

## LangGraph vs. Concourse YAML

| Aspect | Concourse (YAML) | LangGraph (Python) |
|--------|------------------|--------------------|
| Routing | Static predefined | Dynamic, LLM-driven conditional edges |
| State | Stateless containers | First-class typed shared state + checkpoints |
| Failure recovery | Re-run from start | Time travel, per-node retries, resume from checkpoint |
| Human-in-loop | Not native | First-class `interrupt()` |
| Parallelism | Static `in_parallel` | Static fan-out + dynamic `Send` API |
| Introspection | Build logs | LangGraph Studio, LangSmith traces |

## Observability

- LangSmith: automatic tracing with `LANGCHAIN_TRACING_V2=true`; zero code changes
- Every node execution, LLM call, tool invocation captured as nested spans
- Metrics: token usage, latency P50/P99, error rates, cost breakdowns
- OTEL export supported — integrate with existing Jaeger/Grafana stacks
- Alternative: Langfuse (open-source, self-hosted)

## Recommendations for Lintel

1. **One subgraph per agent role** — planner, coder, reviewer, pm, designer, summarizer as individual StateGraphs
2. **AsyncPostgresSaver** — shares Lintel's existing asyncpg/PostgreSQL infrastructure
3. **`interrupt()` for Slack approval flows** — pause, surface to Slack thread, resume on reply
4. **OTEL export into existing observability stack** — avoid LangSmith as mandatory SaaS dependency
5. **`stream_mode=["messages", "updates"]`** — tokens to Slack, state diffs for progress dashboard

## Sources

- https://docs.langchain.com/oss/python/langgraph/graph-api
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/streaming
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- https://docs.langchain.com/oss/python/langgraph/observability
- https://blog.langchain.com/langgraph-platform-ga/
- https://blog.langchain.com/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt/
