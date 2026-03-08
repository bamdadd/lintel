# Software Delivery Lifecycle Requirements

## The Delivery Loop

Every work item flows through a configurable delivery loop. The loop tracks the full lifecycle from desire to learning, and the learnings feed back into the next desire.

```
  +---------+     +---------+     +--------+     +--------+     +---------+     +-------+
  | DESIRE  | --> | DEVELOP | --> | REVIEW | --> | DEPLOY | --> | OBSERVE | --> | LEARN |
  +---------+     +---------+     +--------+     +--------+     +---------+     +-------+
       ^                                                                           |
       +------------- learnings inform next desire --------------------------------+
```

---

## DL-1: Fully Configurable Phases (P1)

### DL-1.1: Phase Sequences

The delivery loop is **fully configurable**. Teams define their own phase sequences per project or per workflow definition.

**Default sequence:** `("desire", "develop", "review", "deploy", "observe", "learn")`

**Configuration:**
- Per project: `Project.delivery_phase_sequence` (see ENT-M9)
- Per workflow: `WorkflowDefinitionRecord.delivery_phases` (see ENT-M11)
- Workflow-level overrides project-level

**Examples of custom sequences:**

| Work Type | Phase Sequence | Why |
|---|---|---|
| Feature | desire → develop → review → deploy → observe → learn | Full cycle |
| Hotfix | desire → develop → deploy → observe | Skip review for emergency fixes |
| Refactor | desire → develop → review → learn | No deploy (internal improvement) |
| Rearchitect | desire → review → develop → review → deploy → observe → learn | Double review |
| Experiment | desire → develop → deploy → observe → observe → learn | Extended observation |

### DL-1.2: Phase Definition

Phases are strings, not an enum. This allows teams to add custom phases:

```python
# Standard phases
"desire", "develop", "review", "deploy", "observe", "learn"

# Custom phases teams might add
"design", "security_review", "load_test", "canary", "rollout", "retrospective"
```

### DL-1.3: Phase Transition Rules

- Forward transition: Always allowed (automatic via events)
- Backward transition: Indicates rework — tracked as a metric
- Skip: Allowed if the phase is not in the sequence
- Custom phase: Must be defined in the sequence to be entered

---

## DL-2: Phase-to-Event Mapping (P1)

Each phase is triggered by specific events. The `DeliveryLoop` entity transitions when it observes the triggering event for the next phase.

### DL-2.1: Desire Phase

- **Entry trigger:** `WorkItemCreated` event
- **Actors:** Human (creates the request via chat, UI, or imported from Jira/Linear)
- **What happens:** Work item is created with clear description and acceptance criteria
- **Events emitted:** `DeliveryLoopStarted`, `DeliveryLoopPhaseTransitioned(→ desire)`
- **Exit trigger:** `WorkflowStarted` or `PipelineRunStarted` — someone or something picked up the work

### DL-2.2: Develop Phase

- **Entry trigger:** `PipelineRunStarted` event for the work item
- **Actors:** AI agents (planner, coder), humans (guidance, pair programming)
- **What happens:** Code is written, committed, pushed. Branch created, changes implemented.
- **Events observed:** `AgentStepScheduled/Started/Completed`, `CommitPushed`, `BranchCreated`
- **Exit trigger:** `PRCreated` event — code is ready for review

### DL-2.3: Review Phase

- **Entry trigger:** `PRCreated` event
- **Actors:** AI reviewer agent, human reviewers
- **What happens:** Code is reviewed, comments added, approval requested
- **Events observed:** `PRCommentAdded`, `ApprovalRequested`, `HumanApprovalGranted/Rejected`
- **Rework loop:** `HumanApprovalRejected` → transition **back to Develop**. This backward transition is tracked as rework in agent/team metrics.
- **Exit trigger:** `HumanApprovalGranted` for merge gate

### DL-2.4: Deploy Phase

- **Entry trigger:** `HumanApprovalGranted` (merge approval) or PR merge event
- **Actors:** CI/CD system, deploy agent
- **What happens:** Code is merged, deployment is triggered to target environment
- **Events observed:** `DeploymentStarted`, `DeploymentSucceeded/Failed`
- **Failure handling:** `DeploymentFailed` → can transition to Develop (fix and redeploy) or trigger rollback
- **Exit trigger:** `DeploymentSucceeded` event

### DL-2.5: Observe Phase

- **Entry trigger:** `DeploymentSucceeded` event
- **Duration:** Configurable observation window (default: 24 hours)
- **Actors:** System (metrics collection), observability integrations (Datadog alerts)
- **What to observe:** Error rates, performance metrics, user feedback, deployment stability
- **Events observed:** `DeliveryMetricComputed`, `IncidentDetected` (if issues arise)
- **Early exit:** `IncidentDetected` triggers early transition to Learn (something went wrong)
- **Exit trigger:** Observation window timer expires with no incidents

### DL-2.6: Learn Phase

- **Entry trigger:** Observation window ends, or `IncidentDetected` forces early learning
- **Actors:** System (automated retrospective), humans (optional review)
- **What happens:** System analyzes the loop's metrics and generates insights:
  - Cycle time for this work item
  - Agent accuracy during development
  - Review turnaround time
  - Deployment success/failure
  - Any guardrails that fired
- **Events emitted:** `LearningCaptured`, `DeliveryLoopCompleted`
- **Output:** Learnings stored on `DeliveryLoop.learnings` as structured data

### DL-2.7: Rework Loops

When an approval is rejected or a deployment fails, the loop can transition backward:

```
Review → (rejection) → Develop → Review → Deploy
Deploy → (failure) → Develop → Review → Deploy
```

Each backward transition:
- Emits `DeliveryLoopPhaseTransitioned` with `from_phase` and `to_phase`
- Increments the rework counter on agent/team metrics
- Is tracked as part of the loop's `phase_history`

---

## DL-3: DeliveryLoop Entity Lifecycle (P1)

### DL-3.1: Creation

When a `WorkItemCreated` event is observed:
1. Check if the work item's project has a `delivery_phase_sequence`
2. If yes, create a `DeliveryLoop` with that sequence
3. Set `current_phase = phase_sequence[0]` (typically "desire")
4. Emit `DeliveryLoopStarted`

### DL-3.2: Phase Transition

When a trigger event for the next phase is observed:
1. Validate the transition is valid (next phase exists in sequence, or backward for rework)
2. Record the transition in `phase_history` with timestamp
3. Update `current_phase`
4. Emit `DeliveryLoopPhaseTransitioned`

### DL-3.3: Completion

When the last phase in the sequence completes:
1. Set `completed_at`
2. Compute total loop duration and per-phase durations
3. Emit `DeliveryLoopCompleted` with duration metrics

### DL-3.4: Implementation Location

Create `domain/delivery_loop/loop_manager.py`:
- EventBus subscriber
- Subscribes to phase trigger events
- Manages DeliveryLoop lifecycle via CRUD store

---

## DL-4: Continuous Improvement (P2)

### DL-4.1: Automated Retrospectives

After each `DeliveryLoopCompleted`, the system generates a retrospective:

**What went well:**
- Fast cycle time (below team average)
- High agent accuracy (above threshold)
- Quick review turnaround

**What could improve:**
- Rework detected (N backward transitions)
- Slow review time (above average)
- High token usage (cost concern)
- Test failures (quality concern)

**Suggested actions:**
- Adjust agent prompts (if accuracy declining)
- Add more test coverage (if test failures recurring)
- Change review assignment (if review bottleneck)

### DL-4.2: Rearchitecting Triggers

When metrics trends indicate systemic issues across multiple loops, trigger special workflow types:

| Trend | Threshold | Triggered Action |
|---|---|---|
| Agent accuracy declining over 3 consecutive loops | accuracy_rate < 0.7 | Suggest prompt revision workflow |
| Lead time increasing over 5 consecutive loops | lead_time > 2x baseline | Suggest process simplification |
| Change failure rate spiking | cfr > 0.15 for 3 consecutive periods | Suggest additional testing stages |
| Rework ratio high | rework_ratio > 0.3 for 3 loops | Suggest architecture review |

These are implemented as `GuardrailRule` instances with `trigger_event_type="DeliveryLoopCompleted"` and metric thresholds that look at trends across multiple loops.

### DL-4.3: Learning Feed-Forward

Learnings captured during the Learn phase can inform future work:

1. **Agent prompt tuning:** If rework category is "review_rejection", adjust the agent's system prompt to address common rejection reasons
2. **Process optimization:** If review time is consistently the bottleneck, suggest auto-merging for low-risk changes
3. **Resource allocation:** If certain agent roles have high accuracy, assign more work to them

This feed-forward loop is what makes Lintel a flywheel, not just a mirror.

---

## DL-5: Work Types and Their Default Loops

### DL-5.1: Feature Development

```
desire → develop → review → deploy → observe → learn
```

Full cycle. All phases. Standard software delivery.

### DL-5.2: Bug Fix

```
desire → develop → review → deploy → observe → learn
```

Same as feature but typically shorter cycle time. Urgency tracked via work item priority.

### DL-5.3: Refactoring

```
desire → develop → review → learn
```

No deploy phase (internal code quality improvement). Learning captures what was refactored and why.

### DL-5.4: Rearchitecting

```
desire → review → develop → review → deploy → observe → learn
```

Double review. First review validates the architecture decision before development starts. Second review validates the implementation.

### DL-5.5: Custom

Teams define any sequence. The platform enforces no constraints on what phases are valid — it only tracks transitions and computes metrics.
