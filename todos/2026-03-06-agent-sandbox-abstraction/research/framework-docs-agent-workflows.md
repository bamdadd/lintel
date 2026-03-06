# Framework Docs: Agent Workflows (LangGraph)

## LangGraph State Management

### TypedDict State
```python
from typing import Annotated, TypedDict
from langgraph.graph import add

class ThreadWorkflowState(TypedDict):
    thread_ref: str
    sandbox_id: str | None  # Only store ID, not live object
    sandbox_results: Annotated[list[dict], add]  # Append-only reducer
```

### Serialization Constraint
- State must be JSON-serializable for checkpointing.
- **Never store** live objects (Docker containers, SDK clients) in state.
- Store only `sandbox_id: str` — look up the live object via runtime context.

## LangGraph InjectedRuntime

### Injecting Services into Tools
```python
from langgraph.prebuilt import InjectedRuntime

@tool
async def run_in_sandbox(
    command: str,
    runtime: Annotated[AgentRuntime, InjectedRuntime],
) -> str:
    sandbox_manager = runtime.sandbox_manager
    result = await sandbox_manager.execute(sandbox_id, SandboxJob(command=command))
    return result.stdout
```

### Runtime Context Setup
```python
runtime = AgentRuntime(
    sandbox_manager=sandbox_manager,
    # ... other services
)

graph = create_graph()
result = await graph.ainvoke(state, config={"runtime": runtime})
```

### Why InjectedRuntime
- Tools need access to infrastructure services
- State is for data flow, not service injection
- Runtime context is the LangGraph-idiomatic DI mechanism
- Survives graph serialization/checkpointing

## LangGraph ToolNode

### Exposing Sandbox as Tool
```python
from langgraph.prebuilt import ToolNode

tools = [run_in_sandbox, read_sandbox_file, write_sandbox_file]
tool_node = ToolNode(tools)

graph.add_node("tools", tool_node)
graph.add_edge("agent", "tools")
graph.add_edge("tools", "agent")
```

### Tool Return Values
- Tools return strings that go back to the agent as tool results.
- For structured data, serialize to JSON string.
- Keep tool outputs concise — LLMs have context limits.

## Workflow Node Pattern

### Implement Node (Target Integration)
```python
async def spawn_implementation(state: ThreadWorkflowState) -> dict:
    # 1. Create sandbox
    sandbox_id = await manager.create(config, thread_ref)

    # 2. Clone repo
    await manager.execute(sandbox_id, SandboxJob(command=f"git clone {repo_url} /workspace"))

    # 3. Run implementation (agent loop with tools)
    # ... agent uses sandbox tools via ToolNode

    # 4. Collect artifacts
    artifacts = await manager.collect_artifacts(sandbox_id)

    # 5. Destroy sandbox
    await manager.destroy(sandbox_id)

    return {"sandbox_results": [artifacts], "sandbox_id": None}
```
