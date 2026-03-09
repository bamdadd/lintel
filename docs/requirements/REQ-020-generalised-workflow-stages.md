# REQ-020: Generalised Workflow Stages

**Status:** Draft
**Priority:** High
**Created:** 2026-03-09

---

## Problem

Workflow stages are hard-coded in `feature_to_pr.py` with a fixed LangGraph node sequence and a static `NODE_TO_STAGE` mapping. The `WorkflowDefinitionRecord` stores graph structure (`graph_nodes`, `graph_edges`, `step_configs`) but the executor ignores it — always running the same hard-coded graph. Users cannot compose, configure, or extend workflows through the UI.

## Goal

Make workflow stages fully data-driven, modular, and pluggable. Users compose custom pipelines from a catalogue of reusable step types via the UI. The backend executes exactly the graph the user defined. New node types can be added by implementing a single interface — no changes to graph code, executor, or stage tracking.

---

## Design Principles

| Principle | Application |
|-----------|------------|
| **Single Responsibility** | Each node type is a self-contained unit: one handler, one schema, one concern |
| **Open/Closed** | New node types are added by registration, not by modifying existing code. The executor, compiler, and stage tracker are closed for modification, open for extension |
| **Liskov Substitution** | All node handlers conform to the `NodeHandler` protocol — any handler is interchangeable at any position in the graph |
| **Interface Segregation** | Node types declare only the capabilities they need (approval support, sandbox access, agent runtime) via fine-grained protocols |
| **Dependency Inversion** | The executor depends on `NodeRegistry` (abstraction), not on concrete node modules. Node handlers depend on `NodeContext` (abstraction), not on `app_state` |

---

## Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────────┐
│                    UI Editor                         │
│  Stage Palette │ ReactFlow Canvas │ Config Panel     │
└───────────────────────┬─────────────────────────────┘
                        │ save / validate
┌───────────────────────▼─────────────────────────────┐
│                 API Layer                            │
│  workflow-definitions  │  stage-types  │  pipelines  │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Graph Compiler                          │
│  WorkflowDefinitionRecord → StateGraph → compile()  │
│  Resolves node_type → handler via NodeRegistry       │
│  Generates routers from conditional edge specs       │
│  Computes interrupt_before from step_configs         │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Workflow Executor                        │
│  astream() │ stage tracking │ interrupt/resume       │
│  Delegates to compiled graph — no knowledge of       │
│  specific node types                                 │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Node Registry                           │
│  node_type → NodeDescriptor (handler, schema, meta)  │
│  Built-in nodes │ Plugin nodes │ Project-scoped nodes│
└─────────────────────────────────────────────────────┘
```

---

## Core Abstractions

### NodeHandler Protocol

```python
class NodeHandler(Protocol):
    async def __call__(
        self, state: ThreadWorkflowState, config: RunnableConfig | None = None,
    ) -> dict[str, Any]: ...
```

Every node type implements this single interface. The executor and compiler only depend on this protocol.

### NodeDescriptor

```python
@dataclass(frozen=True)
class NodeDescriptor:
    node_type: str                          # unique key: "research", "implement", etc.
    handler: NodeHandler                    # the async callable
    label: str                              # human-readable: "Research Codebase"
    description: str
    category: NodeCategory                  # enum: CODE, QUALITY, APPROVAL, INTEGRATION, CUSTOM
    config_schema: dict[str, Any]           # JSON Schema for per-instance config
    input_keys: tuple[str, ...]             # required state keys consumed
    output_keys: tuple[str, ...]            # state keys produced
    supports_approval: bool = False         # can be gated with interrupt_before
    supports_retry: bool = True
    default_timeout_seconds: int = 300
```

### NodeRegistry Protocol

```python
class NodeRegistry(Protocol):
    def register(self, descriptor: NodeDescriptor) -> None: ...
    def get(self, node_type: str) -> NodeDescriptor: ...
    def list_all(self) -> list[NodeDescriptor]: ...
    def list_by_category(self, category: NodeCategory) -> list[NodeDescriptor]: ...
```

The executor and compiler depend on this abstraction, never on concrete node modules.

### GraphCompiler Protocol

```python
class GraphCompiler(Protocol):
    def compile(
        self,
        definition: WorkflowDefinitionRecord,
        registry: NodeRegistry,
        checkpointer: Any,
    ) -> CompiledStateGraph: ...

    def validate(
        self,
        definition: WorkflowDefinitionRecord,
        registry: NodeRegistry,
    ) -> list[ValidationError]: ...
```

Separated from the executor — testable in isolation, replaceable.

### RoutingCondition

```python
@dataclass(frozen=True)
class RoutingCondition:
    field: str          # state key to inspect
    operator: str       # "eq", "neq", "in", "contains", "truthy", "falsy"
    value: object       # comparison value
    goto: str           # target node name

@dataclass(frozen=True)
class ConditionalEdgeSpec:
    source: str
    conditions: tuple[RoutingCondition, ...]
    default: str        # fallback target
```

The compiler generates Python callables from these specs via a `RouterFactory`.

---

## Requirements

### R1 — Node Registry (Plugin Architecture)

- **R1.1** `NodeRegistry` is an in-memory registry populated at startup. Built-in nodes are registered via a `register_builtin_nodes()` function.
- **R1.2** Each node type is a `NodeDescriptor` with handler, schema, I/O contract, and metadata. The descriptor is the single source of truth — `NODE_TO_STAGE` is derived from it, not maintained separately.
- **R1.3** Registration is idempotent. Duplicate `node_type` keys raise at startup (fail-fast).
- **R1.4** Plugin entry point: third-party packages expose nodes via a `lintel.node_plugins` entry point group. At startup, the registry discovers and registers plugin descriptors.
- **R1.5** Project-scoped nodes: a `WorkflowDefinitionRecord` can reference node types scoped to a project (stored as code artifacts). These are registered lazily when the definition is compiled.

### R2 — Graph Compiler

- **R2.1** `LangGraphCompiler` implements `GraphCompiler`. It builds a `StateGraph` from `WorkflowDefinitionRecord` by resolving each node's `node_type` against the registry and wiring edges.
- **R2.2** Conditional edges use `ConditionalEdgeSpec` → `RouterFactory.make_router()` to generate callables.
- **R2.3** `interrupt_before` is computed from `step_configs` where `requires_approval=True`, not hard-coded at compile time.
- **R2.4** Validation at save time:
  - Unreachable nodes (not connected from entry point)
  - Missing entry point
  - References to unregistered node types
  - Cycles without exit conditions
  - I/O mismatches (upstream node doesn't produce keys that downstream node requires)
- **R2.5** Compiled graphs are cached by `(definition_id, content_hash)`. Cache is invalidated when definition is updated.
- **R2.6** The existing `feature_to_pr` graph becomes a seeded `WorkflowDefinitionRecord` with `is_template: true`, compiled through the same `GraphCompiler` path. No special-case code.

### R3 — Executor Decoupling

- **R3.1** `WorkflowExecutor` receives a `GraphCompiler` and `NodeRegistry` via constructor injection. It never imports concrete node modules.
- **R3.2** Stage tracking derives stage names from the registry: `registry.get(node_type).label`, not from a static dict.
- **R3.3** The executor is node-type-agnostic. Adding/removing node types requires zero changes to executor code.
- **R3.4** `PipelineRun` stores `workflow_definition_version` (content hash) at creation time. Resume always uses the same compiled graph version.

### R4 — Stage Catalogue API

- **R4.1** `GET /api/v1/stage-types` returns all registered node descriptors.
- **R4.2** Response shape per item:
  ```json
  {
    "node_type": "research",
    "label": "Research Codebase",
    "description": "...",
    "category": "code",
    "config_schema": { /* JSON Schema */ },
    "input_keys": ["repo_url", "sandbox_id"],
    "output_keys": ["research_context"],
    "supports_approval": true,
    "supports_retry": true,
    "default_timeout_seconds": 300
  }
  ```
- **R4.3** Categories: `code`, `quality`, `approval`, `integration`, `custom`.

### R5 — Workflow Editor UI

- **R5.1** Side palette listing available stage types from the catalogue API, grouped by category. Drag-and-drop to add steps to the ReactFlow canvas.
- **R5.2** Per-node config panel: form auto-generated from `config_schema` (JSON Schema → form). Fields: model selector, agent role, timeout, custom prompt, approval toggle.
- **R5.3** Edge validation: visual error indicators for invalid connections (I/O mismatch, unreachable nodes).
- **R5.4** "Use Template" button: forks a built-in template into an editable custom definition.
- **R5.5** Validate button: calls backend validation endpoint, surfaces errors inline on the canvas.
- **R5.6** Data flow visualisation: shows which output keys from upstream feed into downstream input keys.

### R6 — Step Configuration & Overrides

- **R6.1** `WorkflowStepConfig` extended with: `model_id`, `timeout_seconds`, `retry_policy { max_retries, backoff_seconds }`, `custom_prompt_template`, `env_vars`.
- **R6.2** Config merge order: step config → project defaults → global defaults. Step wins.
- **R6.3** Approval gating is a boolean on `WorkflowStepConfig.requires_approval`, not a separate node type. The compiler inserts `interrupt_before` automatically.

### R7 — I/O Contract Enforcement

- **R7.1** Before running a node, the executor validates that all `input_keys` declared by the descriptor are present in the workflow state.
- **R7.2** After a node completes, the executor validates that `output_keys` were produced. Missing outputs emit a warning event (soft failure — allows graceful degradation).
- **R7.3** The UI editor displays I/O flow: upstream outputs → downstream inputs, with type annotations where available.

---

## Phased Delivery

### Phase 1 — Foundation (Node Registry + Compiler)
| Item | Description |
|------|------------|
| `NodeDescriptor` + `NodeRegistry` | Core abstractions, in-memory implementation |
| `register_builtin_nodes()` | Wrap existing 10 node handlers as descriptors |
| `LangGraphCompiler` | Build StateGraph from WorkflowDefinitionRecord |
| `RouterFactory` | Generate routing callables from `ConditionalEdgeSpec` |
| Seed template | Convert `feature_to_pr` to a seeded `WorkflowDefinitionRecord` |
| Wire executor | Inject compiler + registry, remove hard-coded graph import |
| Stage catalogue API | `GET /api/v1/stage-types` |
| Tests | Compiler validation, registry, round-trip compile + execute |

### Phase 2 — Editor UI
| Item | Description |
|------|------------|
| Stage palette | Fetch from catalogue API, grouped by category, drag-and-drop |
| Config panel | JSON Schema → Mantine form for selected node |
| Template forking | "Use Template" → editable copy |
| Validation feedback | Inline errors from backend validation |

### Phase 3 — Advanced Configuration
| Item | Description |
|------|------------|
| Step config overrides | model, timeout, retry, prompt template per step |
| I/O contract validation | Pre/post node checks, warning events |
| Edge validation UI | Visual I/O mismatch indicators |
| Data flow overlay | Show key flow on canvas edges |

### Phase 4 — Extensibility
| Item | Description |
|------|------------|
| Plugin entry points | `lintel.node_plugins` setuptools group |
| Project-scoped nodes | Custom handlers stored as code artifacts |
| Subgraph composition | Node type that delegates to another compiled workflow |
| Community marketplace | Discovery + install of third-party node packages |

---

## LangGraph Implementation Notes

Based on research (see `REQ-020-research-langgraph-dynamic-workflows.md`):

1. **Dynamic `StateGraph` construction** is fully supported — loop over nodes/edges, then `compile()`
2. **Cache compiled graphs** by `(definition_id, content_hash)` to avoid per-request rebuild
3. **`interrupt_before` can be passed per-invocation** via config — no recompile needed for approval changes
4. **Conditional routing** requires Python callables, but `RouterFactory.make_router()` generates them from `ConditionalEdgeSpec` data
5. **Checkpointing with topology changes** is mostly safe (channels are versioned), but pin definition version per PipelineRun to avoid drift
6. **Subgraph composition** works via `parent.add_node("name", compiled_subgraph)` with automatic namespace isolation
7. **Config loss after interrupt/resume** — already solved with `_runtime_registry.py`

---

## Out of Scope

- Multi-tenant workflow definitions (single-tenant for now)
- Visual step-through debugging in the editor
- Parallel execution within a pipeline (sequential-only in Phase 1–3; `Send` API for Phase 4)
- Version history / diff for workflow definitions

---

## Success Criteria

1. A user can create a custom workflow in the UI by dragging steps from a palette, configuring each step, connecting edges, and saving.
2. The backend executes exactly the user-defined graph — no hard-coded paths.
3. The existing `feature_to_pr` workflow works as a seeded template with zero behaviour change.
4. Adding a new node type requires only: (a) implement `NodeHandler`, (b) create `NodeDescriptor`, (c) call `registry.register()` — zero changes to executor, compiler, or stage tracking.
5. All abstractions are protocol-based — every component is testable in isolation with fakes/stubs.
