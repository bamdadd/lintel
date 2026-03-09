# REQ-020 Research: Dynamic Workflow Stages with LangGraph

**Date:** 2026-03-09

## Executive Summary

LangGraph fully supports building `StateGraph` instances dynamically from data structures at runtime. The recommended approach for Lintel is a **hybrid**: build the graph dynamically from each `WorkflowDefinitionRecord` using a node registry, cache compiled graphs by `(definition_id, version)`, and pin each `PipelineRun` to the definition version at creation time to avoid mid-flight topology drift.

---

## 1. Current Lintel LangGraph Usage

### Graph Construction (`feature_to_pr.py`)
- `StateGraph(ThreadWorkflowState)` with hard-coded `add_node` / `add_edge` / `add_conditional_edges` calls
- 14 nodes, 3 approval gates with `interrupt_before`
- Compiled with `AsyncPostgresSaver` for checkpointing
- Single graph topology for all workflow definitions

### Node Handler Signature
```python
async def node_handler(state: ThreadWorkflowState, config: RunnableConfig | None = None) -> dict[str, Any]:
```
- Receives full state + `RunnableConfig` with services in `config["configurable"]`
- Returns partial state dict (LangGraph merges into state)

### Execution (`workflow_executor.py`)
- `graph.astream(input, config=config)` yields `{node_name: output_dict}` chunks
- `graph.get_state(config).next` detects interrupt pauses
- Resume via `graph.astream(None, config)` (None input = continue from checkpoint)

### Known Issue: Config Loss After Interrupt
- LangGraph strips custom `configurable` keys on resume
- Solved with `_runtime_registry.py` — a module-level dict keyed by `run_id`

---

## 2. LangGraph Dynamic Graph Capabilities

### 2.1 Dynamic Graph Construction ✅
Build `StateGraph` from a data structure — loop over nodes/edges, then `compile()`:

```python
def build_graph_from_definition(defn: WorkflowDefinitionRecord, registry: NodeRegistry) -> StateGraph:
    builder = StateGraph(ThreadWorkflowState)
    for node in defn.graph_nodes:
        builder.add_node(node.name, registry.get_handler(node.node_type))
    for edge in defn.graph_edges:
        builder.add_edge(edge.source, edge.target)
    for cedge in defn.conditional_edges:
        builder.add_conditional_edges(cedge.source, make_router(cedge.conditions))
    builder.set_entry_point(defn.entry_point)
    return builder
```

**Constraint:** Once compiled, graph is immutable. Rebuild for structural changes. Cache by `(definition_id, version_hash)`.

### 2.2 Conditional Routing from Data ✅
`add_conditional_edges` requires a Python callable, but you can generate it from config:

```python
def make_router(conditions: list[RoutingCondition]) -> Callable[[State], str]:
    def router(state: State) -> str:
        for cond in conditions:
            if state.get(cond.field) == cond.value:
                return cond.goto
        return cond.default
    return router
```

### 2.3 Subgraph Composition ✅
Two patterns supported:
- **Shared state:** `parent.add_node("sub", compiled_subgraph)` — auto-routes matching channel names
- **Different schema:** wrap in a function that maps parent ↔ child state

Subgraph checkpoints are namespace-isolated automatically.

### 2.4 interrupt_before — Dynamic Per-Invocation ✅
Can be passed at invocation time via config, not just at compile time:
```python
graph.invoke(input, config={"interrupt_before": ["node_x"]})
```
This means approval-required nodes can be computed from the workflow definition without recompiling.

### 2.5 Checkpointing with Topology Changes
- **Adding nodes** between runs: safe — new channels start from defaults
- **Removing nodes:** safe — stale channel values are orphaned but harmless
- **Renaming nodes:** effectively adds new + abandons old
- **Recommendation:** Pin each PipelineRun to the definition version at creation time. Never hot-swap topology on a live thread.

### 2.6 Send API for Dynamic Fan-Out
Conditional edges can return `[Send("node", payload1), Send("node", payload2)]` for runtime parallelism without rebuilding the graph.

### 2.7 LangGraph Platform Assistants
Multiple "assistants" from the same graph, each with different `config`. Closest built-in primitive to user-defined workflow variants. No built-in visual workflow builder for end users.

---

## 3. Approaches Compared

### A: Static Graph + Config Injection
- Graph compiled once, cached, reused
- Variation via `configurable` per node
- **Pros:** Stable checkpointing, no rebuild overhead, Studio-compatible
- **Cons:** Cannot add/remove node types at runtime

### B: Fully Dynamic Graph from Definition
- Build `StateGraph` from `WorkflowDefinitionRecord` at request time
- Node registry maps `node_type → handler`
- **Pros:** Maximum flexibility — arbitrary DAG topologies
- **Cons:** Must rebuild on definition change, mid-flight definition changes are unsafe

### Recommended: Hybrid (B with caching)
- Build dynamically from definition, cache by `(definition_id, version_hash)`
- Pin PipelineRun to definition version at creation
- Pass `interrupt_before` per-invocation from definition config
- This gives full flexibility with stable execution

---

## 4. Key Gotchas

| Issue | Impact | Mitigation |
|-------|--------|------------|
| `interrupt()` index ordering | Resume misaligns if interrupt call order changes | Use `interrupt_before` (name-based) not `interrupt()` (index-based) |
| Non-idempotent side effects before interrupt | Re-executed on resume | Place side effects after interrupt or guard with idempotency checks |
| Config loss after interrupt/resume | Custom `configurable` keys stripped | Runtime registry pattern (already implemented) |
| Checkpoint topology drift | Stale data for removed nodes | Pin definition version per PipelineRun |
| Conditional edges must be callables | Can't store routing logic as pure data | `make_router()` factory generates callables from condition specs |

---

## 5. Sources

| Source | Tier | Key Finding |
|--------|------|-------------|
| [LangGraph Docs — Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) | Official | Shared-state and wrapper-function composition patterns |
| [LangGraph Docs — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Official | interrupt_before vs interrupt(), index-based resume, idempotency |
| [LangGraph Docs — Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) | Official | StateGraph compile, Send API, immutability post-compile |
| [LangGraph Docs — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Official | thread_id cursor, subgraph namespace isolation, checkpointer inheritance |
| [LangGraph Blog — v0.2](https://blog.langchain.com/langgraph-v0-2/) | Official | Modular checkpoint libs, v3→v4 auto-migration |
| [LangGraph Forum — Dynamic Graphs](https://forum.langchain.com/t/dynamic-graph-creation-at-runtime/1387) | Community | Send API, template graphs, Assistants for variants |
| [DeepWiki — Checkpoint Implementations](https://deepwiki.com/langchain-ai/langgraph/4.2-checkpoint-implementations) | Community | Channel versioning, incremental delta storage |
