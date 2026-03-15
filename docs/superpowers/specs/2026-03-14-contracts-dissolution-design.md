# Contracts Dissolution Design

## Summary

Dissolve the centralised `lintel-contracts` package by moving domain-specific types, protocols, errors, commands, events, and data models into their relevant domain packages. Keep a slim `lintel-contracts` with only the shared event-sourcing kernel.

**Goal:** A change to sandbox errors no longer triggers tests for all 15 packages — only the sandbox package and its direct dependents.

## What stays in `lintel-contracts`

The shared event-sourcing kernel used by nearly every package:

### `types.py`
- `ThreadRef`, `ActorType`, `CorrelationId`, `EventId`

### `events.py`
- `EventEnvelope`, `EVENT_TYPE_MAP`, `deserialize_event()`
- Individual event dataclasses move to their domain packages (see below)

### `protocols.py`
- `EventHandler`, `EventBus`, `CommandDispatcher`, `EventStore`

Everything else is dissolved.

## Type migration map

### `lintel-sandbox` (`packages/sandbox/src/lintel/sandbox/`)

**New files:** `types.py`, `errors.py`, `events.py`

Types:
- `SandboxConfig`, `SandboxJob`, `SandboxResult`, `SandboxStatus`

Protocols (into `protocols.py`):
- `SandboxManager`

Errors:
- `SandboxError`, `SandboxNotFoundError`, `SandboxTimeoutError`, `SandboxExecutionError`, `NoSandboxAvailableError`

Events:
- `SandboxCreated`, `SandboxCommandExecuted`, `SandboxFileWritten`, `SandboxArtifactsCollected`, `SandboxDestroyed`, `SandboxJobScheduled`

### `lintel-models` (`packages/models/src/lintel/models/`)

**New files:** `types.py`, `errors.py`, `events.py`

Types:
- `AIProvider`, `AIProviderType`, `ModelPolicy`, `Model`, `ModelAssignment`, `ModelAssignmentContext`

Protocols (into `protocols.py`):
- `ModelRouter`

Errors:
- `ClaudeCodeCredentialError`

Events:
- `AIProviderCreated`, `AIProviderUpdated`, `AIProviderRemoved`, `AIProviderApiKeyUpdated`
- `ModelRegistered`, `ModelUpdated`, `ModelRemoved`, `ModelAssignmentCreated`, `ModelAssignmentRemoved`
- `ModelSelected`, `ModelCallCompleted`

Stream events (`stream_events.py`):
- `StreamEvent`, `InitializeStep`, `StartStep`, `FinishStep`, `ToolCallEvent`, `ToolResultEvent`, `LogEvent`, `StatusEvent`, `EndEvent`

### `lintel-agents` (`packages/agents/src/lintel/agents/`)

**New files:** `types.py`, `commands.py`, `events.py`

Types:
- `AgentRole`, `AgentCategory`, `AgentSession`, `AgentDefinitionRecord`
- `SkillDescriptor`, `SkillResult`, `SkillExecutionMode`, `SkillCategory`, `SkillDefinition`

Protocols (into existing or new `protocols.py`):
- `Skill`, `SkillRegistry`

Commands:
- `ScheduleAgentStep`, `ScheduleSandboxJob`

Events:
- `AgentStepScheduled`, `AgentStepStarted`, `AgentStepCompleted`
- `AgentDefinitionCreated`, `AgentDefinitionUpdated`, `AgentDefinitionRemoved`
- `SkillRegistered`, `SkillUpdated`, `SkillRemoved`, `SkillInvoked`, `SkillSucceeded`, `SkillFailed`

### `lintel-pii` (`packages/pii/src/lintel/pii/`)

**New files:** `protocols.py`, `commands.py`, `events.py`

Protocols:
- `Deidentifier`, `DeidentifyResult`, `PIIVault`

Commands:
- `RevealPII`

Events:
- `PIIDetected`, `PIIAnonymised`, `PIIResidualRiskBlocked`
- `VaultRevealRequested`, `VaultRevealGranted`

### `lintel-repos` (`packages/repos/src/lintel/repos/`)

**New files:** `types.py`, `protocols.py`, `commands.py`, `events.py`

Types:
- `Repository`, `RepoStatus`

Protocols:
- `RepositoryStore`, `RepoProvider`

Commands:
- `RegisterRepository`, `UpdateRepository`, `RemoveRepository`

Events:
- `RepositoryRegistered`, `RepositoryUpdated`, `RepositoryRemoved`
- `RepoCloned`, `BranchCreated`, `CommitPushed`, `PRCreated`, `PRCommentAdded`

### `lintel-persistence` (`packages/persistence/src/lintel/persistence/`)

**New files:** `types.py`, `protocols.py`, `commands.py`, `data_models.py`

Types:
- `Credential`, `CredentialType`, `TokenStatus`

Protocols:
- `CredentialStore`

Commands:
- `StoreCredential`, `RevokeCredential`

Data models (all Pydantic models from `data_models.py`):
- `ChatMessage`, `ConversationData`, `ConnectionData`, `GeneralSettings`
- `AgentDefinitionData`, `SandboxMetadata`, `ReportVersion`, `CacheStats`, `LLMResponse`
- `ComplianceConfig`, `ProjectData`, `WorkItemData`, `TagData`, `BoardColumnData`, `BoardData`
- `ThreadStatusData`, `TaskBacklogEntry`

Events:
- `CredentialStored`, `CredentialRevoked`

### `lintel-slack` (`packages/slack/src/lintel/slack/`)

**New files:** `protocols.py`, `commands.py`, `events.py`

Protocols:
- `ChannelAdapter`

Commands:
- `ProcessIncomingMessage`, `GrantApproval`, `RejectApproval`

Events:
- `ThreadMessageReceived`

### `lintel-observability` (`packages/observability/src/lintel/observability/`)

**New files:** `protocols.py`, `events.py`

Protocols:
- `StepMetricsRecorder`

Events:
- `AuditRecorded`
- `DeliveryMetricComputed`, `AgentPerformanceComputed`, `HumanPerformanceComputed`

### `lintel-workflows` (`packages/workflows/src/lintel/workflows/`)

**New files:** `types.py`, `commands.py`, `events.py`

Types:
- `PipelineRun`, `PipelineStatus`, `Stage`, `StageAttempt`, `StageStatus`, `WorkflowPhase`
- `WorkflowDefinitionRecord`, `WorkflowStepConfig`

Commands:
- `StartWorkflow`

Events:
- `WorkflowStarted`, `WorkflowAdvanced`, `IntentRouted`
- `PipelineRunStarted`, `PipelineStageCompleted`, `PipelineRunCompleted`, `PipelineRunFailed`, `PipelineRunCancelled`, `PipelineRunDeleted`
- `PipelineStageApproved`, `PipelineStageRejected`, `PipelineStageRetried`, `StageReportEdited`, `StageReportRegenerated`

### `lintel-projections` (`packages/projections/src/lintel/projections/`)

Move entire `projections.py`:
- `ProjectionState`, `ProjectionStatus`, `Projection`, `ProjectionStore`, `ProjectionEngine`

### `lintel-domain` (`packages/domain/src/lintel/domain/`)

**New files:** `types.py`, `events.py`

All remaining domain entity types:
- Projects: `Project`, `ProjectStatus`
- Work items: `WorkItem`, `WorkItemStatus`, `WorkItemType`
- Boards: `Tag`, `Board`, `BoardColumn`
- Approvals: `ApprovalRequest`, `ApprovalStatus`
- Audit: `AuditEntry`
- Users: `User`, `UserRole`, `Team`
- Notifications: `NotificationChannel`, `NotificationRule`
- Governance: `Policy`, `PolicyAction`
- Environment: `Environment`, `EnvironmentType`, `Variable`
- Triggers: `Trigger`, `TriggerType`, `WorkflowHook`, `HookType`
- Automation: `AutomationDefinition`, `AutomationTriggerType`, `ConcurrencyPolicy`
- Artifacts: `CodeArtifact`, `TestVerdict`, `TestResult`
- Resources: `ResourceVersion`, `PassedConstraint`, `JobInput`
- MCP: `MCPServer`, `ChatSession`
- Delivery loop: `DeliveryLoop`, `PhaseTransitionRecord`, `DEFAULT_DELIVERY_PHASES`
- All compliance types: `Regulation`, `CompliancePolicy`, `Procedure`, `Practice`, `Strategy`, `KPI`, `Experiment`, `ComplianceMetric`, `KnowledgeEntry`, `ArchitectureDecision`, `KnowledgeExtractionRun` + all related enums (`ComplianceStatus`, `RiskLevel`, `KPIDirection`, `ExperimentStatus`, `KnowledgeEntryType`, `ExtractionStatus`, `ADRStatus`)

All remaining domain events (projects, work items, boards, tags, users, teams, approvals, notifications, settings, hooks, compliance, deployment, guardrails, delivery loop, etc.)

## Dependency graph changes

Current: every package depends on `lintel-contracts`.

After:
- `lintel-contracts` — slim kernel (no domain deps)
- `lintel-sandbox` — depends on `lintel-contracts` (for `ThreadRef`)
- `lintel-models` — depends on `lintel-contracts`
- `lintel-agents` — depends on `lintel-contracts`, `lintel-sandbox` (for `SandboxJob`/`SandboxResult`), `lintel-models` (for `ModelPolicy`)
- `lintel-pii` — depends on `lintel-contracts`
- `lintel-repos` — depends on `lintel-contracts`
- `lintel-persistence` — depends on `lintel-contracts`
- `lintel-slack` — depends on `lintel-contracts`
- `lintel-observability` — depends on `lintel-contracts`
- `lintel-domain` — depends on `lintel-contracts`, `lintel-agents` (for `AgentRole`, `AgentCategory`)
- `lintel-workflows` — depends on `lintel-contracts`, `lintel-agents`, `lintel-sandbox`
- `lintel-event-bus` — depends on `lintel-contracts`
- `lintel-event-store` — depends on `lintel-contracts`
- `lintel-projections` — depends on `lintel-contracts`, `lintel-event-bus`
- `lintel-app` — depends on all above

## EVENT_TYPE_MAP handling

`EVENT_TYPE_MAP` in `contracts/events.py` is a registry mapping event type strings to classes. After dissolution, event classes live in different packages. Two options:

**Chosen approach:** Each domain package registers its events into a shared registry via a `register_events()` function. The app package calls all registrations at startup. `EVENT_TYPE_MAP` becomes a mutable dict populated at boot time rather than a static dict.

## Migration approach

**Big bang** — move everything at once, update all imports in one pass. No re-export bridges.

### Steps per target package:
1. Create new type/protocol/error/command/event files in the target package
2. Move the relevant classes from contracts to the new files
3. Update all `from lintel.contracts.X import Y` to `from lintel.<pkg>.X import Y` across all consumers
4. Update `pyproject.toml` dependencies
5. Run package tests to verify

### Order of operations:
1. Leaf packages first (no domain deps): `lintel-sandbox`, `lintel-models`, `lintel-pii`, `lintel-repos`, `lintel-observability`
2. Mid-tier: `lintel-agents`, `lintel-persistence`, `lintel-slack`, `lintel-projections`
3. Core domain: `lintel-domain`, `lintel-workflows`
4. Slim down contracts (remove moved code, update `EVENT_TYPE_MAP`)
5. Update app package imports
6. Run full test suite

## Testing

After migration:
- `make test-unit` must pass
- `make lint` must pass
- `make typecheck` must pass
- Changing `lintel-sandbox/errors.py` should only trigger `lintel-sandbox`, `lintel-workflows`, `lintel-agents`, `lintel-app` tests — not `lintel-pii` or `lintel-repos`
