# REQ-035: Parallel Agent Execution with Shared Sandbox & Live Monitoring

**Status**: Draft
**Date**: 2026-03-14
**Priority**: P2

## Context

Today each workflow stage runs a single agent in a single sandbox. The implement stage writes code, then a separate review stage evaluates it. This serial approach means the coder gets no real-time feedback — review happens after the fact.

We want agents to run **in parallel within the same stage**, sharing one sandbox, with independent log streams and a grouped visualisation.

---

## Motivating Example

During the **implement** stage, two agents share one sandbox:

1. **Coder agent** — writes code, commits after each logical change
2. **Code reviewer agent** — watches diffs since last check, writes feedback into `REVIEW.md`
3. Coder agent reads `REVIEW.md` after each commit and addresses feedback before proceeding

This creates a tight, continuous feedback loop without waiting for a separate review stage.

---

## REQ-035.1: Multi-Agent Stage Execution

**Effort:** Small

A workflow stage can declare multiple agents that run concurrently in the same sandbox.

### Requirements

- `StageConfig` gains an `agents` field: `list[AgentStageConfig]`
- Each `AgentStageConfig` specifies: `role`, `is_primary` (bool), `tools`, `model_override`
- All agents share the same sandbox (filesystem, git repo, environment)
- Each agent has its own `AgentRuntime` instance with separate LLM context
- Stage completes when:
  - The **primary** agent signals done, OR
  - All agents signal done
  - Configurable via `completion_strategy: primary_completes | all_complete`
- If any agent fails, the stage fails (configurable: `fail_fast: true | false`)
- Backward compatible: stages with no `agents` field behave as today (single agent)

### Events

- `AgentStarted(run_id, stage_name, agent_role, agent_instance_id)`
- `AgentCompleted(run_id, stage_name, agent_role, outcome, duration)`
- `AgentFailed(run_id, stage_name, agent_role, error)`

---

## REQ-035.2: Independent Agent Log Streams

**Effort:** Small

Each agent in a parallel group gets its own log stream, filterable by role.

### Requirements

- Logs tagged with `agent_role` and `agent_instance_id`
- SSE endpoint streams all agents' logs with discriminator:
  ```json
  {"agent": "coder", "type": "chunk", "content": "Writing auth middleware..."}
  {"agent": "reviewer", "type": "chunk", "content": "Reviewing diff: +42 -3 lines..."}
  ```
- Per-agent log API:
  - `GET /api/v1/pipelines/{run_id}/stages/{stage}/agents` — list active agents in stage
  - `GET /api/v1/pipelines/{run_id}/stages/{stage}/agents/{role}/logs` — stream one agent's logs
- Combined stream (existing endpoint) includes all agents, tagged

---

## REQ-035.3: Pipeline Visualisation — Parallel Agent Groups

**Effort:** Medium

### Design Concept

When a stage has parallel agents, the stage card expands to show a **grouped container** with individual agent lanes:

```
┌─ implement ──────────────────────────────────────────────┐
│  ┌─────────────────────────────┬─────────────────────────┐│
│  │ 🔵 coder                   │ 🟢 reviewer             ││
│  │ ● running (2m 14s)         │ ● running (2m 14s)      ││
│  │                            │                          ││
│  │ Writing auth middleware... │ Reviewing diff #3...     ││
│  │ Adding JWT validation...   │ ✓ No issues in diff #2   ││
│  │ Committing: add auth...    │ ⚠ Missing error handle  ││
│  │                            │   → wrote REVIEW.md      ││
│  │ [View full log ↗]          │ [View full log ↗]        ││
│  └─────────────────────────────┴─────────────────────────┘│
│  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱  coder                     │
│  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱  reviewer                  │
│  2 of 2 running                                          │
└──────────────────────────────────────────────────────────┘
```

### Requirements

- Stage box contains a **parallel group container** with subtle border/background differentiating it from single-agent stages
- Inside the group: **side-by-side agent cards** (horizontal on desktop, stacked on mobile), each showing:
  - Agent role icon + name
  - Live status indicator (running / idle / waiting / done / failed)
  - Scrolling log tail (last 5 lines, auto-scroll)
  - Click to expand full log view (modal or panel)
- Group footer shows:
  - **Aggregate status**: "2 of 2 running", "1 of 2 done", "complete"
  - **Timeline bars**: overlapping horizontal bars showing each agent's execution duration
- Single-agent stages render **unchanged** — no visual regression
- Responsive: on narrow screens, agent cards stack vertically

### Interaction

- Click agent card → expand to full-screen log view for that agent
- Toggle between "combined" (interleaved) and "split" (side-by-side) log views
- Agent cards show a subtle pulse animation while actively streaming

---

## REQ-035.4: Agent Communication Protocol

**Effort:** Small

File-based inter-agent communication within the shared sandbox.

### Convention

```
.lintel/
  signals/
    coder.ready          # Coder drops this after each commit
    reviewer.feedback    # Reviewer writes structured feedback
    reviewer.approved    # Reviewer signals approval (no more issues)
```

### Protocol

1. **Coder** writes code, commits, then creates `.lintel/signals/coder.ready`
2. **Reviewer** watches for `coder.ready`, reads `git diff HEAD~1`, evaluates
3. **Reviewer** writes feedback to `.lintel/signals/reviewer.feedback` (or `reviewer.approved`)
4. **Reviewer** removes `coder.ready` to signal "feedback delivered"
5. **Coder** reads feedback, addresses issues, commits again → goto 1

### Requirements

- Polling-based: each agent checks signal files between LLM iterations (not inotify)
- Poll interval: configurable, default 5 seconds
- Timeout: if no signal received within `signal_timeout` (default 5 minutes), log warning and continue
- Signal files are plain text or markdown — no binary protocol
- `.lintel/` directory created automatically when parallel agents are configured
- Signal files included in agent tool context (agents told about the protocol in their system prompt)

---

## Architecture Notes

### Package Placement

- **`packages/contracts/`**: `AgentStageConfig`, agent events, signal types
- **`packages/workflows/`**: Parallel agent execution logic in stage runner, signal file injection in system prompts
- **`packages/infrastructure/`**: Log stream multiplexing, per-agent log storage
- **`packages/app/`**: New API routes for agent listing and per-agent logs
- **Frontend**: Parallel group visualisation component

### Key Design Decisions

1. **Agents are independent asyncio tasks** within one stage execution — not separate containers or processes
2. **Sandbox is shared** but each agent has its own `AgentRuntime` with separate LLM context, history, and tool permissions
3. **File-based IPC** (not message queues) — keeps it simple, observable (files are visible in sandbox), and debuggable
4. **No shared memory** — agents communicate exclusively through the filesystem
5. **Primary/secondary pattern** — the primary agent (coder) drives progress; secondary agents (reviewer) provide feedback. Stage completion follows the primary.

### Dependencies

- **REQ-020**: Node registry — parallel agent config needs to plug into the stage definition system
- **REQ-028**: WorkflowNode base class — parallel execution wraps the base node pattern

### Future Extensions (not in v1)

- More than 2 agents (e.g., coder + reviewer + security auditor)
- Dynamic agent spawning mid-stage based on code complexity
- WebSocket-based real-time agent communication (upgrade from file polling)
- Agent-to-agent LLM conversation (shared context window)

---

## Research Pointers

- **LangGraph `Send` API**: Fan-out parallelism within a single graph node — may be usable for parallel agent dispatch
- **Cursor / Windsurf**: How they visualise parallel agent activity in their IDE
- **Claude Code parallel agents**: How Claude Code's Agent tool dispatches concurrent sub-agents with independent contexts
