# Guardrails & Safety Requirements

## Philosophy

Guardrails are enablers, not blockers. They let teams move fast by catching problems automatically — before a human needs to intervene. The goal is not to prevent work, but to ensure quality and safety while maximizing autonomy.

**Harness-inspired approach:** Instead of rigid approval chains where every action needs sign-off, use threshold-based auto-escalation. Low-risk actions proceed automatically. Medium-risk actions notify. High-risk actions pause for approval. Critical-risk actions block.

---

## GRD-1: Guardrail Engine Architecture (P0)

### GRD-1.1: Engine Design

The guardrail engine is an EventBus subscriber. On each event, it evaluates all active `GuardrailRule` entities whose `trigger_event_type` matches.

```
EventBus → GuardrailEngine → [evaluate rules] → Command (escalate/block/warn)
                                    |
                                    v
                              MetricsProjections (for threshold checks)
```

**Location:** `domain/guardrails/engine.py` — domain logic, not infrastructure.

### GRD-1.2: Evaluation Flow

For each incoming event:

1. Filter active `GuardrailRule` records where `trigger_event_type == event.event_type`
2. For each matching rule:
   a. Check cooldown — skip if rule fired within `cooldown_seconds`
   b. Evaluate `condition` against event payload
   c. If threshold is defined, query metrics projection for current metric value
   d. If condition and threshold are met → execute action
3. Emit `GuardrailTriggered` event (via command, not directly)

### GRD-1.3: Critical Rule — No Direct Event Emission

Guardrails emit **commands**, never events directly. This prevents circular event chains.

```
Event → GuardrailEngine → PauseWorkflow command → CommandHandler → WorkflowPaused event
                                                                           |
                                                                           v
                                                                    GuardrailEngine sees
                                                                    WorkflowPaused but
                                                                    does NOT re-trigger
                                                                    (different event type)
```

---

## GRD-2: Threshold-Based Auto-Escalation (P0)

### GRD-2.1: Escalation Tiers

| Tier | Action | Example Trigger | What Happens |
|---|---|---|---|
| 0 | `WARN` | Agent rework rate > 20% | Log + notification to team channel |
| 1 | `REQUIRE_APPROVAL` | Agent rework rate > 30% | Pause workflow, request human approval |
| 2 | `BLOCK` | Agent rework rate > 50% | Block execution, escalate to team lead |
| 3 | `AUTO_REMEDIATE` | Cost exceeds budget by 200% | Emergency stop, kill sandbox, notify admin |

### GRD-2.2: Cooldown Mechanism

After a guardrail fires, it enters cooldown for `cooldown_seconds` (default: 300).

- Prevents alert fatigue from rapidly firing rules
- Cooldown state tracked in-memory per (rule_id, project_id)
- If cooldown expires and condition still true → fire again
- Emergency stop (Tier 3) ignores cooldown

### GRD-2.3: Escalation Targets

`GuardrailRule.escalation_target` can be:
- A `user_id` — direct notification to that user
- A `team_id` — notification to team's primary channel
- A `channel_id` — notification to a specific channel
- Empty — use the project's default notification rules

---

## GRD-3: Condition Language (P0)

### GRD-3.1: Phase 1 — Simple Expressions

Format: `field.path operator value`

Operators: `>`, `<`, `>=`, `<=`, `==`, `!=`, `contains`, `in`

Examples:
```
payload.token_usage.total_tokens > 100000
payload.error_count >= 3
payload.status == "failed"
actor_type == "agent"
payload.duration_ms > 300000
```

### GRD-3.2: Phase 2 — CEL (Common Expression Language)

For complex conditions involving multiple fields, boolean logic, or functions:

```cel
payload.token_usage.total_tokens > 100000 && actor_type == "agent"
payload.retry_count > 3 || payload.duration_ms > 600000
size(payload.failures) > 0
```

### GRD-3.3: Evaluator

Create `domain/guardrails/evaluator.py`:
- Phase 1: Simple expression parser and evaluator
- Phase 2: CEL integration via `cel-python` library
- Evaluates conditions against event payload + metadata

---

## GRD-4: Cost Guardrails (P0)

### GRD-4.1: Token Budgets

| Scope | Budget Type | Source Events |
|---|---|---|
| Per-workflow-run | Max tokens for entire run | `ModelCallCompleted` (summed per run) |
| Per-project daily | Max tokens per day per project | `ModelCallCompleted` (summed per project per day) |
| Per-agent-role | Max tokens per agent role per run | `ModelCallCompleted` (filtered by agent_role) |

### GRD-4.2: Cost Computation

Real-time cost from `ModelCallCompleted` events:

```python
cost = (
    event.payload["input_tokens"] * model.cost_per_1k_input_tokens / 1000
    + event.payload["output_tokens"] * model.cost_per_1k_output_tokens / 1000
)
```

**Requires:** `Model.cost_per_1k_input_tokens` and `Model.cost_per_1k_output_tokens` (see ENT-M3).

### GRD-4.3: Budget Enforcement

Example guardrail rules:

```python
# Warn when a single run uses > $5
GuardrailRule(
    name="Run cost warning",
    trigger_event_type="ModelCallCompleted",
    threshold={"metric": "run_cost_usd", "operator": ">", "value": 5.0},
    action=GuardrailAction.WARN,
)

# Pause when a project exceeds $100/day
GuardrailRule(
    name="Project daily budget",
    trigger_event_type="ModelCallCompleted",
    threshold={"metric": "project_daily_cost_usd", "operator": ">", "value": 100.0},
    action=GuardrailAction.REQUIRE_APPROVAL,
    escalation_target="team-leads",
)

# Emergency stop at $500/day
GuardrailRule(
    name="Emergency cost stop",
    trigger_event_type="ModelCallCompleted",
    threshold={"metric": "project_daily_cost_usd", "operator": ">", "value": 500.0},
    action=GuardrailAction.AUTO_REMEDIATE,
    cooldown_seconds=0,  # no cooldown for emergencies
)
```

---

## GRD-5: Sandbox Hardening (P1)

### GRD-5.1: Resource Limits

Extend `SandboxConfig` (`types.py:214`):

| Field | Type | Default | Purpose |
|---|---|---|---|
| `max_disk_mb` | int | 1024 | Prevent disk exhaustion |
| `max_processes` | int | 64 | Prevent fork bombs |
| `seccomp_profile` | str | "default" | Syscall filtering profile |

**Existing limits:** `memory_limit` (512MB), `cpu_quota` (50000), `network_enabled` (false), `timeout_seconds` (3600).

### GRD-5.2: Network Egress Control

Current: Binary `network_enabled` flag.

Enhanced:
- `network_enabled=True` only during clone phase
- After clone, call `SandboxManager.disconnect_network()` (already exists in protocol)
- For MCP tool calls requiring network: temporary allow-list of specific domains

### GRD-5.3: Tool Call Limits

Per-step limits on agent actions:

| Limit | Scope | Default | Purpose |
|---|---|---|---|
| Max tool calls | Per agent step | 50 | Prevent infinite tool loops |
| Max output tokens | Per agent step | 16000 | Prevent token runaway |
| Max file writes | Per sandbox session | 100 | Prevent filesystem abuse |

Configurable per `WorkflowStepConfig` or per `GuardrailRule`.

### GRD-5.4: Artifact Scanning

After sandbox execution, before collecting artifacts:
- Scan for sensitive data (API keys, passwords) in generated code
- Reuse existing PII firewall (`infrastructure/pii/presidio_firewall.py`) for detection
- Block artifact collection if sensitive data detected
- Emit `SecurityViolationDetected` event

---

## GRD-6: Event-Driven Approvals (P1)

### GRD-6.1: Current State

Approval is state-machine driven inside the workflow executor. The executor checks if a stage requires approval, creates an `ApprovalRequest`, and polls for the result.

### GRD-6.2: Target State

Approvals become fully event-driven via the EventBus:

```
Workflow step completes → ApprovalRequested event → EventBus
                                                       |
                                              ┌────────┴────────┐
                                              │                 │
                                    ChannelNotifier       ApprovalProjection
                                    (sends to Slack/      (tracks pending
                                     Discord/Teams)        approvals)

Human clicks approve → HumanApprovalGranted event → EventBus
                                                       |
                                              WorkflowResumeSubscriber
                                              (emits ResumeWorkflow command)
```

**Benefits:**
- Workflow executor doesn't need to know about channels
- Approval logic is decoupled from workflow execution
- Easy to add new approval channels (just add a new subscriber)
- Approval timeout becomes a simple scheduler that emits `ApprovalExpired` after N minutes

### GRD-6.3: Multi-Approver Support

Via `GuardrailRule`:

```python
GuardrailRule(
    name="Require 2 approvals for production deploy",
    trigger_event_type="ApprovalRequested",
    condition="payload.gate_type == 'merge_approval' and payload.environment == 'production'",
    threshold={"metric": "approval_count", "operator": "<", "value": 2},
    action=GuardrailAction.REQUIRE_APPROVAL,
)
```

---

## GRD-7: Pre-Built Guardrail Rules (P1)

Ship with sensible defaults that teams can customize:

| Rule | Trigger | Condition | Action |
|---|---|---|---|
| Agent rework warning | `HumanApprovalRejected` | rework_rate > 0.2 for agent | WARN |
| Cost warning | `ModelCallCompleted` | run_cost > $5 | WARN |
| Cost escalation | `ModelCallCompleted` | project_daily_cost > $100 | REQUIRE_APPROVAL |
| Sandbox timeout | `SandboxCommandExecuted` | duration > 30min | WARN |
| Test failure block | `TestRunCompleted` | verdict == "failed" | BLOCK (prevent deploy) |
| Large diff review | `PRCreated` | lines_changed > 500 | REQUIRE_APPROVAL |
| PII in artifacts | `SandboxArtifactsCollected` | pii_detected == true | BLOCK |
