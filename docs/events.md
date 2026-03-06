# Event Reference

All events extend `EventEnvelope` with shared metadata:

| Field | Type | Description |
|---|---|---|
| `event_id` | UUID | Unique event identifier |
| `event_type` | str | Discriminator (class name) |
| `schema_version` | int | For upcasting on schema changes |
| `occurred_at` | datetime | UTC timestamp |
| `actor_type` | ActorType | `human`, `agent`, or `system` |
| `actor_id` | str | Who triggered the event |
| `thread_ref` | ThreadRef? | Associated thread (if any) |
| `correlation_id` | UUID | Groups related events |
| `causation_id` | UUID? | Direct cause event |
| `payload` | dict | Event-specific data |
| `idempotency_key` | str? | Deduplication key |

## Channel & ingestion events

- **ThreadMessageReceived** — A message was received in a thread
- **PIIDetected** — PII entities were found in text
- **PIIAnonymised** — Text was anonymized with placeholders
- **PIIResidualRiskBlocked** — Message blocked due to high PII risk

## Workflow events

- **IntentRouted** — Message intent was classified and routed
- **WorkflowStarted** — A workflow instance was created
- **WorkflowAdvanced** — Workflow moved to a new phase

## Agent events

- **AgentStepScheduled** — An agent step was queued
- **AgentStepStarted** — An agent began executing a step
- **AgentStepCompleted** — An agent finished a step
- **ModelSelected** — A model was chosen for an agent call
- **ModelCallCompleted** — An LLM call finished

## Sandbox events

- **SandboxJobScheduled** — A sandbox job was queued
- **SandboxCreated** — A sandbox container was created
- **SandboxArtifactsCollected** — Artifacts were collected from sandbox
- **SandboxDestroyed** — A sandbox container was destroyed

## Repo events

- **BranchCreated** — A git branch was created
- **PRCreated** — A pull request was created

## Approval events

- **HumanApprovalGranted** — A human approved an action
- **HumanApprovalRejected** — A human rejected an action

## Skill events

- **SkillInvoked** — A skill was called
- **SkillSucceeded** — A skill completed successfully
- **SkillFailed** — A skill execution failed

## Security events

- **VaultRevealRequested** — A PII reveal was requested
- **VaultRevealGranted** — A PII reveal was authorized
- **PolicyDecisionRecorded** — A security policy decision was recorded
