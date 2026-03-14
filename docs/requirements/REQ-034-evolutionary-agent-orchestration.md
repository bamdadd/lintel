# REQ-034: Evolutionary Agent Orchestration

**Status**: Draft
**Date**: 2026-03-14
**Inspired by**: Hyperspace AGI (v3.0.10), E2B, Karpathy autoresearch loop

## Context

We dispatched 93 work items simultaneously, creating 40+ concurrent Docker sandboxes. All failed due to resource exhaustion — containers killed, commands timed out, workspaces vanished. The platform lacks concurrency control, cross-run learning, and any mechanism for agents to share discoveries.

Hyperspace (by @varun_mathur) demonstrates that autonomous agents on commodity hardware can converge on correct results through distributed evolutionary search and cross-pollination — 32,868 commits from 237 agents across 5 domains with zero human intervention.

This REQ captures the patterns they have that we don't.

---

## REQ-034.1: Concurrency Limiter & Work Queue

**What Hyperspace has**: Agents run within resource budgets on commodity hardware (M3 Max, GTX 1060). The network self-regulates participation based on available compute.

**What we have**: `asyncio.create_task()` with no limits. `max_concurrent_workflows` exists in settings but is never enforced.

**What we need**:

### 034.1.1 — Semaphore-gated workflow execution
- `WorkflowExecutor` wraps `execute()` with `asyncio.Semaphore(max_concurrent_workflows)`
- Default: 5 concurrent workflows (configurable via settings)
- Excess workflows queue in FIFO order
- Queued workflows visible via `/api/v1/pipelines?status=queued`
- Event: `WorkflowQueued(run_id, position, estimated_wait)`

### 034.1.2 — Sandbox resource budgeting
- Track active sandbox count in `DockerSandboxManager`
- Refuse `create()` when at capacity (return specific error, not timeout)
- Configurable per-sandbox memory/CPU limits already exist — add a global budget
- Health endpoint: `GET /admin/sandbox-pool` returning active/max/queued counts

### 034.1.3 — Backpressure to chat
- When queue depth > threshold, inform the user: "Your request is queued (position N)"
- SSE event on pipeline stream: `{"type": "queued", "position": 3}`

---

## REQ-034.2: Experiment Tracking & Evolutionary Selection

**What Hyperspace has**: Each agent runs mutate → evaluate → share. 30 mutations compete per round. Win rates tracked. Losers pruned, winners amplified. Network converges on optimal.

**What we have**: `Experiment` entity with status/hypothesis/outcome — but it's manual. No automated mutation, evaluation, or selection loop.

**What we need**:

### 034.2.1 — Run-level metrics capture
- Every workflow run records quantitative outcomes: test pass rate, lint score, review verdict, time-to-complete, lines changed, retry count
- Stored as `RunMetric(run_id, metric_name, value, unit)` — not just pass/fail
- Queryable: `GET /api/v1/metrics/runs?project_id=X&metric=test_pass_rate&since=...`

### 034.2.2 — Strategy mutations
- When a workflow fails, the system generates a "mutation" — a modified strategy config:
  - Different model assignment per stage
  - Different prompt template
  - Different tool set enabled
  - Different timeout/retry parameters
- Mutations are tracked as children of the original strategy: `parent_strategy_id`

### 034.2.3 — Tournament selection
- For repeated tasks (e.g., "implement feature from spec"), run N strategy variants
- Compare outcomes on the same task using run metrics
- Promote winning strategies: `strategy.win_rate`, `strategy.generation`
- Prune strategies below threshold after M runs
- Event: `StrategyPromoted(strategy_id, win_rate, generation)`
- Event: `StrategyPruned(strategy_id, reason)`

### 034.2.4 — Experiment-KPI linkage (automated)
- `ComplianceMetric` collection should be automated from run metrics
- When a KPI target is "test pass rate > 95%", the system auto-collects from runs
- Close the loop: KPI → Experiment → Strategy → Run → Metric → KPI

---

## REQ-034.3: Cross-Run Knowledge Sharing (Research DAG)

**What Hyperspace has**: Every experiment feeds into a shared Research DAG — a knowledge graph where observations, experiments, and syntheses link across domains. Cross-domain insights propagate: finance pruning → search pruning. An "AutoThinker" loop synthesizes across all domains.

**What we have**: `KnowledgeEntry` for extracted code logic. `CodeArtifact` and `TestResult` per run. But artifacts are isolated per run — no cross-run graph, no synthesis.

**What we need**:

### 034.3.1 — Run observation capture
- After each workflow run, extract structured observations:
  - What worked (successful patterns, model choices, prompt structures)
  - What failed (error categories, timeout causes, test failures)
  - Quantitative metrics (from 034.2.1)
- Stored as `Observation(observation_id, run_id, project_id, domain, content, tags)`
- Event: `ObservationRecorded(observation_id, run_id)`

### 034.3.2 — Knowledge graph (DAG)
- Observations link to experiments link to syntheses
- Edges: `inspired_by`, `contradicts`, `extends`, `supersedes`
- Lineage tracking: which observation led to which strategy mutation
- Depth chains: track how many generations of improvement led to current best
- Query: `GET /api/v1/knowledge/graph?project_id=X&domain=implementation`

### 034.3.3 — Cross-project synthesis
- An LLM-based "synthesizer" periodically reads recent observations across projects
- Generates hypotheses: "Pattern X worked in project A, try in project B"
- Hypotheses become new `Experiment` entries with `source: synthesis`
- Event: `SynthesisGenerated(synthesis_id, source_observations[])`

### 034.3.4 — Playbook curation
- When a strategy wins consistently (win_rate > threshold over N runs), distill it into a reusable "playbook"
- Playbook = frozen strategy config + explanation of why it works
- New projects bootstrap from playbooks instead of starting cold
- `Playbook(playbook_id, strategy_config, explanation, domain, win_rate, source_project_ids)`

---

## REQ-034.4: Agent Gossip & Discovery

**What Hyperspace has**: P2P gossip network. Agents share discoveries via shortcodes. CRDT swarm catalog for network-wide discovery. Peers review each other's experiments. RSS feed integration.

**What we have**: Agents are isolated. Each workflow step runs one agent role in one sandbox. No inter-agent communication.

**What we need**:

### 034.4.1 — Agent result broadcast
- When an agent completes a step, broadcast the outcome to a shared event stream
- Other active agents (in concurrent workflows) can subscribe to relevant broadcasts
- Filter by domain/project/tag to avoid noise
- Event: `AgentDiscoveryBroadcast(agent_role, run_id, discovery_type, summary)`

### 034.4.2 — Peer review of agent outputs
- Before promoting a strategy, another agent instance reviews the evidence
- Adversarial pattern: a "risk officer" agent vetoes low-confidence outputs
- This already maps to our review node — extend it to cross-workflow review

### 034.4.3 — Agent leaderboard
- Track per-agent-role performance: which model+prompt combos produce best results
- `GET /api/v1/agents/leaderboard?role=coder&metric=test_pass_rate`
- Feed leaderboard data back into model assignment (REQ-021)

---

## REQ-034.5: Warps (Declarative Configuration Presets)

**What Hyperspace has**: "Warps" — composable configuration presets that transform agent behavior. `power-mode`, `add-research-causes`, `optimize-inference`, `privacy-mode`. 12 curated + community-contributed.

**What we have**: Static agent definitions with role/prompt/tools. Settings are global. No composable presets.

**What we need**:

### 034.5.1 — Workflow presets (warps)
- Declarative YAML/JSON configs that modify workflow behavior:
  - `fast-mode`: skip research stage, use fastest model, reduce review cycles to 0
  - `thorough-mode`: add research, use best model, 3 review cycles, extended timeouts
  - `privacy-mode`: local models only, no external API calls, no telemetry
  - `cost-optimized`: cheapest models, aggressive caching, minimal retries
- Presets are composable: `fast-mode + privacy-mode`
- `POST /api/v1/workflows/presets` to register, `GET` to list
- Apply via: `POST /api/v1/chat {"message": "...", "preset": "thorough-mode"}`

### 034.5.2 — Per-project defaults
- Projects can set a default preset
- Override per-conversation or per-work-item

---

## REQ-034.6: Autoswarm (Goal-Driven Swarm Dispatch)

**What Hyperspace has**: `hyperspace swarm new "optimize CSS themes for WCAG"` — describe a goal in plain English, the network creates a distributed swarm to solve it. LLM generates sandboxed experiment code, validates locally, publishes to P2P network.

**What we have**: Single workflow per work item. No parallel experimentation on the same goal.

**What we need**:

### 034.6.1 — Swarm dispatch
- Given a goal, spawn N parallel workflows with different strategy mutations
- Each workflow runs independently in its own sandbox
- Results converge: pick the best outcome based on metrics
- `POST /api/v1/swarms {"goal": "...", "variants": 5, "project_id": "..."}`
- Event: `SwarmCreated(swarm_id, goal, variant_count)`
- Event: `SwarmConverged(swarm_id, winning_run_id, metric_values)`

### 034.6.2 — Resource-aware scheduling
- Swarm respects the concurrency limiter (034.1)
- Variants queue behind each other if resources are constrained
- Early termination: if one variant clearly wins, cancel remaining
- Budget cap: max total LLM cost per swarm

---

## REQ-034.7: Continuous Autonomous Loop

**What Hyperspace has**: Agents run continuously — 9,178+ cycles, journal entries, autonomous experimentation overnight. The system self-improves by running experiments on its own infrastructure.

**What we have**: Request-response only. A human sends a message, a workflow runs, it completes. No autonomous continuation.

**What we need**:

### 034.7.1 — Scheduled experimentation
- Register recurring experiments: "Every night, re-run failing strategies with mutations"
- Ties into REQ-032 (scheduled jobs) but specifically for experimentation
- `trigger_type: schedule`, `schedule: "0 2 * * *"` (2am daily)

### 034.7.2 — Cycle tracking
- Track experiment cycles: `cycle_number`, `personal_best`, `network_best`
- Journal: append-only log of what each cycle discovered
- Dashboard: `GET /api/v1/experimentation/cycles?project_id=X`

### 034.7.3 — Self-improvement loop
- The platform runs experiments on its own workflows
- Example: "Which model produces fewest review rejections for Python code?"
- Meta-experimentation: the system optimizes its own configuration

---

## Priority & Sequencing

| REQ | Impact | Effort | Priority |
|-----|--------|--------|----------|
| 034.1 Concurrency limiter | Fixes 55% of current failures | S | **P0 — Do first** |
| 034.2 Experiment tracking | Foundation for everything else | M | **P1** |
| 034.3 Knowledge DAG | Compounds value over time | L | P2 |
| 034.5 Warps/presets | Quick UX win | S | P2 |
| 034.4 Agent gossip | Requires concurrent agents | M | P3 |
| 034.6 Autoswarm | Requires 034.1 + 034.2 | L | P3 |
| 034.7 Autonomous loop | Requires 034.2 + 034.6 | L | P4 |

---

## Mapping to Existing Lintel Primitives

| Hyperspace Concept | Lintel Equivalent | Gap |
|---|---|---|
| Agent on P2P network | Workflow in sandbox | No P2P, no gossip |
| Mutation round | Strategy config | No automated mutation |
| Win rate tracking | KPI + ComplianceMetric | Not automated from runs |
| Research DAG | KnowledgeEntry + Observation | No graph edges, no synthesis |
| Warp | (none) | Need preset system |
| Swarm | (none) | Need parallel variant dispatch |
| Cycle | Pipeline run | No continuous cycling |
| Playbook | (none) | Need distilled strategy templates |
| AutoThinker | (none) | Need cross-domain synthesis agent |
| CRDT catalog | (none) | Need distributed state (future) |
