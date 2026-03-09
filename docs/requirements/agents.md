# Agent Architecture

All agent-related code lives in `src/lintel/agents/`. Workflow nodes in `src/lintel/workflows/nodes/` invoke agents via `AgentRuntime`.

---

## Agent Roles

Defined in `contracts/types.py:45` as `AgentRole(StrEnum)`:

| Role | Value | Used in Node | Category |
|---|---|---|---|
| `PLANNER` | `planner` | `plan.py` | Engineering |
| `CODER` | `coder` | `implement.py` | Engineering |
| `REVIEWER` | `reviewer` | `review.py` | Quality |
| `PM` | `pm` | `triage.py` | Leadership |
| `DESIGNER` | `designer` | — | Design |
| `SUMMARIZER` | `summarizer` | — | Communication |
| `ARCHITECT` | `architect` | — | Engineering |
| `QA_ENGINEER` | `qa_engineer` | — | Quality |
| `DEVOPS` | `devops` | — | Operations |
| `SECURITY` | `security` | — | Quality |
| `RESEARCHER` | `researcher` | `analyse.py`, `research.py` | Engineering |
| `TECH_LEAD` | `tech_lead` | — | Leadership |
| `DOCUMENTATION` | `documentation` | — | Communication |
| `TRIAGE` | `triage` | — | Leadership |

## Agent Categories

Defined in `contracts/types.py:36` as `AgentCategory(StrEnum)`:

- `ENGINEERING` — planner, coder, architect, researcher
- `QUALITY` — reviewer, qa_engineer, security
- `OPERATIONS` — devops
- `LEADERSHIP` — pm, tech_lead, triage
- `COMMUNICATION` — summarizer, documentation
- `DESIGN` — designer

---

## AgentRuntime

**File:** `agents/runtime.py:32`

Core execution engine for agent steps. Orchestrates model calls, tool loops, and event emission.

### Key methods

| Method | Purpose |
|---|---|
| `execute_step()` | Non-streaming agent execution with tool loop (up to `max_iterations`) |
| `execute_step_stream()` | Streaming variant — calls `on_chunk` for each content piece |

### Dependencies

- `EventStore` — emits `AgentStepStarted`, `ModelSelected`, `ModelCallCompleted`, `AgentStepCompleted`
- `ModelRouter` — selects model via `select_model()`, calls via `call_model()` / `stream_model()`
- `MCPToolClient` (optional) — gathers and executes MCP server tools
- `SandboxManager` (optional) — executes sandbox-backed tools

### Tool loop

1. Gathers MCP tools from all enabled servers + any explicitly passed tools
2. Calls model with messages + tools
3. If model returns `tool_calls`, dispatches each (sandbox or MCP), appends results, re-calls model
4. Repeats up to `max_iterations` (default: 20)
5. Aggregates token usage across all iterations

---

## Sandbox Tools

**File:** `agents/sandbox_tools.py`

Provides 4 sandbox-backed tools in litellm/OpenAI format:

| Tool | Description |
|---|---|
| `sandbox_read_file` | Read file contents from sandbox workspace |
| `sandbox_write_file` | Write content to a file in sandbox |
| `sandbox_list_files` | List directory contents |
| `sandbox_execute_command` | Run shell command in sandbox |

All tool names prefixed with `sandbox_`. Dispatched via `dispatch_sandbox_tool()`.

---

## Agent Definitions (User-Editable)

**Entity:** `AgentDefinitionRecord` (`types.py:682`)

Persisted agent configurations that can be customised per project. Includes system prompt, model overrides, and tool permissions.

**Entity:** `SkillDefinition` (`types.py:662`)

User-editable skill definitions that extend agent capabilities. Categorised by `SkillCategory` enum.

---

## Workflow Integration

Workflow nodes create agent steps by:

1. Building a message list (system prompt + context from prior stages)
2. Optionally creating a sandbox (`SandboxManager.create()`)
3. Calling `AgentRuntime.execute_step()` with the agent role, messages, and tools
4. Extracting structured output from the model response
5. Cleaning up sandbox if created

See `src/lintel/workflows/nodes/` for per-node implementations.
