# Codebase Survey: Agent Workflows

## LangGraph Workflow State

### `src/lintel/workflows/state.py`
- `ThreadWorkflowState` is a `TypedDict` — JSON-serializable.
- Contains `sandbox_results: Annotated[list[dict], add]` — append-only reducer.
- **Missing**: `sandbox_id: str | None` — no way to track which sandbox is active for the workflow.
- State must be JSON-serializable — no live objects (Docker containers, SDK clients).

## Workflow Definition

### `src/lintel/workflows/feature_to_pr.py`
- LangGraph `StateGraph` with nodes: `ingest`, `plan`, `implement`, `review`, `merge`.
- Conditional edges based on `WorkflowPhase`.
- `implement` node is the integration point for sandbox execution.

## Workflow Nodes

### `src/lintel/workflows/nodes/implement.py`
- **Placeholder implementation** — returns hardcoded data.
- Does NOT call `SandboxManager`.
- Should: create sandbox, clone repo, execute implementation commands, collect artifacts.

### Other nodes (ingest, plan, review)
- Follow the pattern: receive `ThreadWorkflowState`, emit events, return state updates.
- Use `asyncio.to_thread` for any sync operations.

## Agent Runtime

### `src/lintel/agents/runtime.py`
- `AgentRuntime` class with `tools: list[dict[str, Any]]` — opaque tool definitions.
- Tools are passed to LLM provider.
- Sandbox operations should be exposed as tools via LangGraph `ToolNode`.
- LangGraph `InjectedRuntime` is the correct DI mechanism for injecting `SandboxManager` into tool functions.

## Agent Roles

### `src/lintel/contracts/types.py`
- `AgentRole`: `PLANNER`, `CODER`, `REVIEWER`, `PM`, `DESIGNER`, `SUMMARIZER`.
- `CODER` role is the primary sandbox consumer.
- `REVIEWER` may also need sandbox access (for running tests on PR code).

## Integration Pattern
The correct integration is:
1. `SandboxManager` wired into `app.state` via lifespan
2. Passed to LangGraph runtime context via `InjectedRuntime`
3. Workflow nodes access via runtime context (not state)
4. Only `sandbox_id: str` stored in `ThreadWorkflowState`
5. Sandbox lifecycle managed by workflow node (create at start of implement, destroy at end)
