# REQ-028: Migrate Workflow Nodes to Pydantic Classes

**Status:** Proposed
**Priority:** Medium
**Category:** Refactoring / Code Quality

## Problem

Workflow nodes in `src/lintel/workflows/nodes/` are implemented as bare async functions with significant issues:

1. **Repeated boilerplate** — Every node re-imports `_stage_tracking`, `_runtime_registry`, `_codebase_context`, builds `ThreadRef`, and wires up `_on_chunk`/`_on_activity` callbacks identically.
2. **Deferred imports everywhere** — Imports are scattered inside function bodies to avoid circular deps, making dependencies invisible.
3. **No shared interface** — Each node function has a slightly different signature and return shape. There's no enforced contract.
4. **Untestable in isolation** — Because dependencies (runtime, sandbox, stage tracker) are resolved inside the function, you can't inject mocks without monkeypatching.
5. **Growing god-functions** — `implement.py` has 17 functions and 943 lines; `setup_workspace.py` has 580+ lines. Logic that belongs in the class is spread across module-level helpers.

## Proposed Solution

Introduce a `WorkflowNode` base class (Pydantic `BaseModel`) that each node extends. LangGraph accepts any callable — a `__call__` method on an instance works.

### Base Class

```python
# src/lintel/workflows/nodes/base.py

from pydantic import BaseModel
from typing import Any
from langchain_core.runnables import RunnableConfig
from lintel.workflows.state import ThreadWorkflowState


class WorkflowNode(BaseModel):
    """Base class for all workflow graph nodes."""

    model_config = {"arbitrary_types_allowed": True}

    # Injected at graph construction time
    agent_runtime: AgentRuntime
    sandbox_manager: SandboxManager

    async def execute(
        self, state: ThreadWorkflowState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Override in subclasses."""
        raise NotImplementedError

    async def __call__(
        self, state: ThreadWorkflowState, config: RunnableConfig
    ) -> dict[str, Any]:
        """LangGraph entry point — wraps execute with stage tracking & error handling."""
        return await self.execute(state, config)

    # Shared helpers available to all nodes
    def build_thread_ref(self, state: ThreadWorkflowState) -> ThreadRef: ...
    async def track_stage(self, config, stage_name, state, **kw): ...
    async def on_chunk(self, config, chunk: str): ...
    async def on_activity(self, config, activity: str): ...
```

### Example Migration — `analyse.py`

Before (bare function):
```python
async def analyse_code(state, config):
    from lintel.workflows.nodes._stage_tracking import mark_started, mark_completed, ...
    from lintel.workflows.nodes._codebase_context import gather_codebase_context
    ...
```

After (class):
```python
class AnalyseNode(WorkflowNode):
    system_prompt: str = ANALYSE_SYSTEM_PROMPT

    async def execute(self, state, config):
        await self.track_stage(config, "analyse", state, status="running")
        context = await self.gather_codebase_context(state)
        result = await self.agent_runtime.invoke(...)
        await self.track_stage(config, "analyse", state, status="completed")
        return {"analysis": result}
```

### Graph Registration

```python
# Before
graph.add_node("analyse", analyse_code)

# After
graph.add_node("analyse", AnalyseNode(
    agent_runtime=runtime,
    sandbox_manager=sandbox,
))
```

## Migration Plan

### Phase 1: Foundation
- [ ] Create `WorkflowNode` base class in `nodes/base.py`
- [ ] Extract shared helpers (`_stage_tracking`, `_notifications`, `_codebase_context`) into base class methods
- [ ] Add unit tests for base class

### Phase 2: Simple Nodes First
- [ ] `route.py` → `RouteNode` (simplest, no agent/sandbox deps)
- [ ] `approval_gate.py` → `ApprovalGateNode`
- [ ] `ingest.py` → `IngestNode`
- [ ] `triage.py` → `TriageNode`

### Phase 3: Core Workflow Nodes
- [ ] `analyse.py` → `AnalyseNode`
- [ ] `plan.py` → `PlanNode`
- [ ] `research.py` → `ResearchNode`
- [ ] `review.py` → `ReviewNode`
- [ ] `test_code.py` → `TestCodeNode`

### Phase 4: Complex Nodes
- [ ] `implement.py` → `ImplementNode` (+ extract `TddStrategy` / `StructuredStrategy` sub-classes)
- [ ] `setup_workspace.py` → `SetupWorkspaceNode` (+ extract credential helpers)
- [ ] `close.py` → `CloseNode` (+ extract PR creation logic)

### Phase 5: Cleanup
- [ ] Remove module-level helper files that are now base class methods (`_stage_tracking.py`, `_notifications.py`, etc.)
- [ ] Update graph builder to instantiate node classes
- [ ] Update all tests

## Benefits

- **Dependency injection** — Runtime, sandbox, and services injected at construction, not resolved at call time
- **Testability** — Instantiate nodes with mock dependencies, no monkeypatching
- **Shared interface** — `WorkflowNode` protocol enforced by the type system
- **Reduced duplication** — Stage tracking, chunk callbacks, thread ref building done once in base class
- **Pydantic validation** — Configuration validated at graph build time, not at runtime deep in a function
- **Decomposition** — Large nodes (`implement`, `setup_workspace`) naturally split into strategy classes

## Constraints

- LangGraph nodes must be callables `(state, config) -> dict` — the `__call__` method satisfies this
- Migration must be incremental — old functions and new classes can coexist in the graph during transition
- No behaviour changes — this is a pure structural refactor

## Files Affected

| File | Lines | Functions | Complexity |
|------|-------|-----------|------------|
| `implement.py` | 943 | 17 | High |
| `setup_workspace.py` | 580+ | 7 | High |
| `close.py` | 360+ | 4 | Medium |
| `research.py` | 207 | 4 | Medium |
| `plan.py` | 207 | 5 | Medium |
| `review.py` | 178 | 2 | Medium |
| `analyse.py` | 169 | 2 | Low |
| `triage.py` | 130 | 3 | Low |
| `test_code.py` | 199 | 2 | Medium |
| `route.py` | 35 | 1 | Low |
| `approval_gate.py` | 50 | 1 | Low |
| `generic.py` | 75 | 2 | Low |
