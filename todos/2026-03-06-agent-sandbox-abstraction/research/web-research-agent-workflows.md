# Web Research: Agent Workflows

## Sandbox-as-Tool Architecture (2024-2025)

### Key Sources
- [WEB-01] Anthropic — "Building Effective Agents" (2025) — recommends tool-based sandbox access
- [WEB-05] LangChain — "Agent Sandbox Patterns" (2025) — Pattern B (sandbox-as-tool)
- [WEB-10] Cursor/Codex — architecture analysis (2025)

### Pattern B: Sandbox-as-Tool (Recommended)
```
Agent (control plane) --[tool call]--> Sandbox (data plane)
     |                                      |
     | Secrets, API keys                    | No secrets
     | Full network                         | No network (or filtered)
     | Persistent state                     | Ephemeral
```

**Why**:
- Agent retains access to secrets, APIs, and context
- Sandbox has "nothing worth stealing" — only code and test results
- Agent can orchestrate multiple sandboxes
- Clean separation of concerns

### Pattern A: Agent-Inside-Sandbox (Not Recommended for Lintel)
- Agent runs inside the sandbox container
- Needs all secrets/API keys injected
- Single sandbox per agent
- Used by: SWE-agent (early versions), some research systems

## LangGraph + Sandbox Integration Patterns

### Tool-Based Integration
```python
@tool
async def execute_in_sandbox(command: str) -> str:
    """Run a command in the sandbox and return output."""
    result = await sandbox_manager.execute(sandbox_id, SandboxJob(command=command))
    if result.exit_code != 0:
        return f"Error (exit {result.exit_code}):\n{result.stderr}"
    return result.stdout
```

### State Management
- `sandbox_id: str | None` in state — tracks active sandbox
- `sandbox_results: list[dict]` — accumulates outputs
- Never store live objects in state

### Lifecycle in Workflow
1. **Pre-agent**: Create sandbox in workflow node
2. **During agent**: Agent uses sandbox via tools (ToolNode)
3. **Post-agent**: Collect artifacts, destroy sandbox in workflow node

## Multi-Agent Sandbox Sharing

### Patterns
1. **One sandbox per workflow** — simplest, most common
2. **One sandbox per agent** — better isolation, higher resource cost
3. **Shared sandbox with snapshots** — E2B supports this natively

### Recommendation for Lintel
- Start with one sandbox per workflow run
- CODER creates and populates
- REVIEWER can access same sandbox (read-only or with test execution)
- Destroy at workflow completion

## Agent Tool Design for Sandbox

### Best Practices
- Keep tool descriptions clear and concise for LLM
- Return structured output (not raw shell output)
- Include error information in tool response
- Limit output length to avoid context window exhaustion
- Provide `list_files` as a tool — agents need to explore codebases

### Common Tool Set
| Tool | Description | Use Case |
|------|-------------|----------|
| `run_command` | Execute shell command | Build, test, install deps |
| `read_file` | Read file content | Understand existing code |
| `write_file` | Write/create file | Implement changes |
| `list_files` | List directory contents | Navigate codebase |
| `search_files` | Search for patterns | Find relevant code |
