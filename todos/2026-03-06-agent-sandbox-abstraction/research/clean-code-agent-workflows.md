# Clean Code Analysis: Agent Workflows

## Workflow Integration Issues

### Placeholder Implement Node
**Location**: `workflows/nodes/implement.py`
**Severity**: High
**Issue**: Returns hardcoded dict with no sandbox interaction. This is the primary entry point where sandbox should be used.
**Required**: Create sandbox, clone repo, execute agent tools, collect artifacts, destroy sandbox.

### Missing sandbox_id in State
**Location**: `workflows/state.py`
**Severity**: High
**Issue**: `ThreadWorkflowState` has `sandbox_results` but no `sandbox_id`. Cannot track active sandbox.
**Fix**: Add `sandbox_id: str | None = None` to state TypedDict.

### Opaque Tool Definitions
**Location**: `agents/runtime.py`
**Severity**: Medium
**Issue**: `tools: list[dict[str, Any]]` — no type safety on tool definitions. Tools are passed as raw dicts.
**Context**: This is somewhat standard for LLM tool schemas (JSON Schema format). But sandbox tools should be defined as typed Python functions with LangGraph `@tool` decorator.

## State Serialization Concerns

### Live Objects in State
**Issue**: If anyone stores a Docker container object in state, LangGraph checkpointing will fail.
**Prevention**: Only `sandbox_id: str` belongs in state. The live `SandboxManager` instance goes in runtime context.

### sandbox_results Type
**Location**: `workflows/state.py`
**Issue**: `sandbox_results: Annotated[list[dict], add]` — values are `dict[str, Any]` (untyped).
**Consideration**: Could define a `SandboxArtifact` TypedDict for type safety. Low priority.

## Tool Design for Sandbox

### Required Tools
For the `CODER` agent role, these tools should be exposed:
1. `run_command(command: str) -> str` — execute in sandbox
2. `read_file(path: str) -> str` — read file content
3. `write_file(path: str, content: str) -> str` — write file
4. `list_files(path: str) -> str` — list directory contents

### Tool Registration
- Define as functions with `@tool` decorator
- Register in `ToolNode` for the implement subgraph
- Inject `SandboxManager` via `InjectedRuntime`
