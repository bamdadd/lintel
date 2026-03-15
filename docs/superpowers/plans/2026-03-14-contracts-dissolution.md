# Contracts Dissolution Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dissolve the centralised `lintel-contracts` package into domain packages so that changes to domain-specific types only trigger tests for relevant packages.

**Architecture:** Move types, protocols, errors, commands, events, and data models from `lintel-contracts` into their domain packages. Keep a slim `lintel-contracts` with only `ThreadRef`, `ActorType`, `EventEnvelope`, `EVENT_TYPE_MAP`, and core event-sourcing protocols. Update all imports across the monorepo. Convert `EVENT_TYPE_MAP` to a mutable registry populated at app startup.

**Tech Stack:** Python 3.12+, uv workspace, frozen dataclasses, Pydantic, Protocol classes

**Spec:** `docs/superpowers/specs/2026-03-14-contracts-dissolution-design.md`

---

## Pre-flight

- [ ] **Step 1: Create a working branch**
```bash
git checkout -b refactor/dissolve-contracts
```

- [ ] **Step 2: Verify green baseline**
```bash
make lint && make typecheck && make test-unit
```

---

## Chunk 1: Event registry refactor

Before moving any events, convert `EVENT_TYPE_MAP` from a static dict to a mutable registry so domain packages can register their events at import time.

### Task 1: Convert EVENT_TYPE_MAP to mutable registry

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/events.py`

- [ ] **Step 1: Add `register_events()` helper and make `EVENT_TYPE_MAP` mutable**

In `events.py`, replace the static dict comprehension with:

```python
EVENT_TYPE_MAP: dict[str, type[EventEnvelope]] = {}

def register_events(*classes: type[EventEnvelope]) -> None:
    """Register event classes into the global EVENT_TYPE_MAP."""
    for cls in classes:
        EVENT_TYPE_MAP[cls.event_type] = cls
```

Keep all existing event classes in the file for now (they'll be moved out in later tasks). At the bottom, call `register_events()` with all of them so nothing breaks.

- [ ] **Step 2: Run tests to verify nothing breaks**
```bash
make test-unit
```

- [ ] **Step 3: Commit**
```bash
git add packages/contracts/src/lintel/contracts/events.py
git commit -m "refactor: convert EVENT_TYPE_MAP to mutable registry"
```

---

## Chunk 2: Leaf packages (no domain dependencies)

These packages don't depend on other domain packages, so they can be moved first without circular dependency risk.

### Task 2: Move sandbox types, protocols, and errors to `lintel-sandbox`

**Files:**
- Create: `packages/sandbox/src/lintel/sandbox/types.py`
- Create: `packages/sandbox/src/lintel/sandbox/protocols.py`
- Create: `packages/sandbox/src/lintel/sandbox/errors.py`
- Create: `packages/sandbox/src/lintel/sandbox/events.py`
- Modify: `packages/sandbox/pyproject.toml` (ensure `lintel-contracts` dep)
- Modify: all files importing `SandboxConfig`, `SandboxJob`, `SandboxResult`, `SandboxStatus`, `SandboxManager`, sandbox errors, or sandbox events from `lintel.contracts`

**Types to move** (from `contracts/types.py`):
- `SandboxStatus`, `SandboxConfig`, `SandboxJob`, `SandboxResult`

**Protocols to move** (from `contracts/protocols.py`):
- `SandboxManager`

**Errors to move** (from `contracts/errors.py`):
- `SandboxError`, `SandboxNotFoundError`, `SandboxTimeoutError`, `SandboxExecutionError`, `NoSandboxAvailableError`

**Events to move** (from `contracts/events.py`):
- `SandboxJobScheduled`, `SandboxCreated`, `SandboxCommandExecuted`, `SandboxFileWritten`, `SandboxArtifactsCollected`, `SandboxDestroyed`

- [ ] **Step 1: Create `packages/sandbox/src/lintel/sandbox/types.py`**

```python
"""Sandbox domain types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for creating a sandbox container."""
    image: str = "lintel-sandbox:latest"
    memory_limit: str = "4g"
    cpu_quota: int = 200000
    network_enabled: bool = False
    timeout_seconds: int = 3600
    environment: frozenset[tuple[str, str]] = frozenset()
    mounts: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class SandboxJob:
    """A command to execute in a sandbox."""
    command: str
    workdir: str | None = None
    timeout_seconds: int = 300


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandbox command execution."""
    exit_code: int
    stdout: str = ""
    stderr: str = ""
```

- [ ] **Step 2: Create `packages/sandbox/src/lintel/sandbox/errors.py`**

```python
"""Sandbox domain exceptions."""


class SandboxError(Exception):
    """Base for all sandbox errors."""


class SandboxNotFoundError(SandboxError):
    def __init__(self, sandbox_id: str) -> None:
        super().__init__(f"Sandbox not found: {sandbox_id}")
        self.sandbox_id = sandbox_id


class SandboxTimeoutError(SandboxError):
    """Raised when a sandbox operation exceeds its timeout."""


class SandboxExecutionError(SandboxError):
    """Raised when command execution fails unexpectedly."""


class NoSandboxAvailableError(SandboxError):
    """Raised when no sandbox is available in the pool."""
    def __init__(self) -> None:
        super().__init__(
            "No sandbox available in pool. "
            "Pre-provision sandboxes via the API or wait for one to be released."
        )
```

- [ ] **Step 3: Create `packages/sandbox/src/lintel/sandbox/protocols.py`**

```python
"""Sandbox service protocol."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus
    from lintel.contracts.types import ThreadRef


class SandboxManager(Protocol):
    """Manages isolated sandbox environments for agent code execution."""

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str: ...
    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult: ...
    async def execute_stream(self, sandbox_id: str, job: SandboxJob) -> AsyncIterator[str]:
        yield ""  # pragma: no cover
    async def read_file(self, sandbox_id: str, path: str) -> str: ...
    async def write_file(self, sandbox_id: str, path: str, content: str) -> None: ...
    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]: ...
    async def get_status(self, sandbox_id: str) -> SandboxStatus: ...
    async def get_logs(self, sandbox_id: str, tail: int = 200) -> str: ...
    async def collect_artifacts(self, sandbox_id: str, workdir: str = "/workspace") -> dict[str, Any]: ...
    async def reconnect_network(self, sandbox_id: str) -> None: ...
    async def disconnect_network(self, sandbox_id: str) -> None: ...
    async def destroy(self, sandbox_id: str) -> None: ...
```

- [ ] **Step 4: Create `packages/sandbox/src/lintel/sandbox/events.py`**

```python
"""Sandbox domain events."""
from __future__ import annotations

from dataclasses import dataclass
from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class SandboxJobScheduled(EventEnvelope):
    event_type: str = "SandboxJobScheduled"

@dataclass(frozen=True)
class SandboxCreated(EventEnvelope):
    event_type: str = "SandboxCreated"

@dataclass(frozen=True)
class SandboxCommandExecuted(EventEnvelope):
    event_type: str = "SandboxCommandExecuted"

@dataclass(frozen=True)
class SandboxFileWritten(EventEnvelope):
    event_type: str = "SandboxFileWritten"

@dataclass(frozen=True)
class SandboxArtifactsCollected(EventEnvelope):
    event_type: str = "SandboxArtifactsCollected"

@dataclass(frozen=True)
class SandboxDestroyed(EventEnvelope):
    event_type: str = "SandboxDestroyed"

register_events(
    SandboxJobScheduled, SandboxCreated, SandboxCommandExecuted,
    SandboxFileWritten, SandboxArtifactsCollected, SandboxDestroyed,
)
```

- [ ] **Step 5: Update all imports of sandbox types/errors/protocols/events across the codebase**

Find and replace:
- `from lintel.contracts.types import ... SandboxConfig ...` → `from lintel.sandbox.types import SandboxConfig`
- `from lintel.contracts.types import ... SandboxJob ...` → `from lintel.sandbox.types import SandboxJob`
- `from lintel.contracts.types import ... SandboxResult ...` → `from lintel.sandbox.types import SandboxResult`
- `from lintel.contracts.types import ... SandboxStatus ...` → `from lintel.sandbox.types import SandboxStatus`
- `from lintel.contracts.protocols import ... SandboxManager ...` → `from lintel.sandbox.protocols import SandboxManager`
- `from lintel.contracts.errors import ...` → `from lintel.sandbox.errors import ...` (for sandbox errors)
- `from lintel.contracts.events import ... Sandbox... ...` → `from lintel.sandbox.events import ...`

Update `pyproject.toml` dependencies for any package that now imports from `lintel-sandbox`.

- [ ] **Step 6: Remove moved types from contracts**

Remove `SandboxStatus`, `SandboxConfig`, `SandboxJob`, `SandboxResult` from `contracts/types.py`.
Remove `SandboxManager` from `contracts/protocols.py`.
Remove all sandbox errors from `contracts/errors.py`.
Remove sandbox event classes from `contracts/events.py` (and from the `register_events` call).

- [ ] **Step 7: Run tests**
```bash
make lint && make typecheck && make test-unit
```

- [ ] **Step 8: Commit**
```bash
git commit -m "refactor: move sandbox types, protocols, errors, events to lintel-sandbox"
```

---

### Task 3: Move model types, protocols, errors, and events to `lintel-models`

**Files:**
- Create: `packages/models/src/lintel/models/types.py`
- Create: `packages/models/src/lintel/models/errors.py`
- Create: `packages/models/src/lintel/models/protocols.py`
- Create: `packages/models/src/lintel/models/events.py`
- Create: `packages/models/src/lintel/models/stream_events.py`

**Types to move:** `AIProvider`, `AIProviderType`, `ModelPolicy`, `Model`, `ModelAssignment`, `ModelAssignmentContext`

**Protocols to move:** `ModelRouter`

**Errors to move:** `ClaudeCodeCredentialError`

**Events to move:** `AIProviderCreated`, `AIProviderUpdated`, `AIProviderRemoved`, `AIProviderApiKeyUpdated`, `ModelRegistered`, `ModelUpdated`, `ModelRemoved`, `ModelAssignmentCreated`, `ModelAssignmentRemoved`, `ModelSelected`, `ModelCallCompleted`

**Also move:** entire `contracts/stream_events.py` → `packages/models/src/lintel/models/stream_events.py`

- [ ] **Step 1: Create type/error/protocol/event files** (same pattern as Task 2)
- [ ] **Step 2: Update all imports across codebase**
- [ ] **Step 3: Remove moved items from contracts**
- [ ] **Step 4: Run tests:** `make lint && make typecheck && make test-unit`
- [ ] **Step 5: Commit**

---

### Task 4: Move PII protocols, commands, events to `lintel-pii`

**Files:**
- Create: `packages/pii/src/lintel/pii/protocols.py`
- Create: `packages/pii/src/lintel/pii/commands.py`
- Create: `packages/pii/src/lintel/pii/events.py`

**Protocols to move:** `Deidentifier`, `DeidentifyResult`, `PIIVault`

**Commands to move:** `RevealPII`

**Events to move:** `PIIDetected`, `PIIAnonymised`, `PIIResidualRiskBlocked`, `VaultRevealRequested`, `VaultRevealGranted`

- [ ] **Steps:** Same pattern — create files, update imports, remove from contracts, test, commit.

---

### Task 5: Move repo types, protocols, commands, events to `lintel-repos`

**Files:**
- Create: `packages/repos/src/lintel/repos/types.py`
- Create: `packages/repos/src/lintel/repos/protocols.py`
- Create: `packages/repos/src/lintel/repos/commands.py`
- Create: `packages/repos/src/lintel/repos/events.py`

**Types to move:** `Repository`, `RepoStatus`

**Protocols to move:** `RepositoryStore`, `RepoProvider`

**Commands to move:** `RegisterRepository`, `UpdateRepository`, `RemoveRepository`

**Events to move:** `RepositoryRegistered`, `RepositoryUpdated`, `RepositoryRemoved`, `RepoCloned`, `BranchCreated`, `CommitPushed`, `PRCreated`, `PRCommentAdded`

- [ ] **Steps:** Same pattern.

---

### Task 6: Move observability protocol and events to `lintel-observability`

**Files:**
- Create: `packages/observability/src/lintel/observability/protocols.py`
- Create: `packages/observability/src/lintel/observability/events.py`

**Protocols to move:** `StepMetricsRecorder`

**Events to move:** `AuditRecorded`, `DeliveryMetricComputed`, `AgentPerformanceComputed`, `HumanPerformanceComputed`

- [ ] **Steps:** Same pattern.

---

## Chunk 3: Mid-tier packages

### Task 7: Move agent types, protocols, commands, events to `lintel-agents`

**Files:**
- Create: `packages/agents/src/lintel/agents/types.py`
- Create: `packages/agents/src/lintel/agents/protocols.py`
- Create: `packages/agents/src/lintel/agents/commands.py`
- Create: `packages/agents/src/lintel/agents/events.py`
- Modify: `packages/agents/pyproject.toml` (add `lintel-sandbox` dep for `SandboxJob`/`SandboxResult` refs)

**Types to move:** `AgentRole`, `AgentCategory`, `AgentSession`, `AgentDefinitionRecord`, `SkillDescriptor`, `SkillResult`, `SkillExecutionMode`, `SkillCategory`, `SkillDefinition`

**Protocols to move:** `Skill`, `SkillRegistry`

**Commands to move:** `ScheduleAgentStep`, `ScheduleSandboxJob`

**Events to move:** `AgentStepScheduled`, `AgentStepStarted`, `AgentStepCompleted`, `AgentDefinitionCreated`, `AgentDefinitionUpdated`, `AgentDefinitionRemoved`, `SkillRegistered`, `SkillUpdated`, `SkillRemoved`, `SkillInvoked`, `SkillSucceeded`, `SkillFailed`

- [ ] **Steps:** Same pattern. Note: `ScheduleAgentStep` and `ScheduleSandboxJob` reference `AgentRole` and `ThreadRef` — `AgentRole` is now local, `ThreadRef` stays in contracts.

---

### Task 8: Move credential types, protocols, commands, and data models to `lintel-persistence`

**Files:**
- Create: `packages/persistence/src/lintel/persistence/types.py`
- Create: `packages/persistence/src/lintel/persistence/protocols.py`
- Create: `packages/persistence/src/lintel/persistence/commands.py`
- Create: `packages/persistence/src/lintel/persistence/data_models.py`
- Create: `packages/persistence/src/lintel/persistence/events.py`

**Types to move:** `Credential`, `CredentialType`, `TokenStatus`

**Protocols to move:** `CredentialStore`

**Commands to move:** `StoreCredential`, `RevokeCredential`

**Data models to move:** All from `contracts/data_models.py` (`ChatMessage`, `ConversationData`, `ConnectionData`, `GeneralSettings`, `AgentDefinitionData`, `SandboxMetadata`, `ReportVersion`, `CacheStats`, `LLMResponse`, `ComplianceConfig`, `ProjectData`, `WorkItemData`, `TagData`, `BoardColumnData`, `BoardData`, `ThreadStatusData`, `TaskBacklogEntry`)

**Events to move:** `CredentialStored`, `CredentialRevoked`

- [ ] **Steps:** Same pattern. Add `pydantic>=2.10` to `lintel-persistence` deps if not already there.

---

### Task 9: Move slack protocols, commands, events to `lintel-slack`

**Files:**
- Create: `packages/slack/src/lintel/slack/protocols.py`
- Create: `packages/slack/src/lintel/slack/commands.py`
- Create: `packages/slack/src/lintel/slack/events.py`

**Protocols to move:** `ChannelAdapter`

**Commands to move:** `ProcessIncomingMessage`, `GrantApproval`, `RejectApproval`

**Events to move:** `ThreadMessageReceived`

- [ ] **Steps:** Same pattern.

---

### Task 10: Move projection types to `lintel-projections`

**Files:**
- Create: `packages/projections/src/lintel/projections/types.py` (or `protocols.py`)

**Move entire `contracts/projections.py`:** `ProjectionState`, `ProjectionStatus`, `Projection`, `ProjectionStore`, `ProjectionEngine`

- [ ] **Steps:** Same pattern.

---

## Chunk 4: Core domain packages

### Task 11: Move workflow types, commands, events to `lintel-workflows`

**Files:**
- Create: `packages/workflows/src/lintel/workflows/types.py`
- Create: `packages/workflows/src/lintel/workflows/commands.py`
- Create: `packages/workflows/src/lintel/workflows/events.py`

**Types to move:** `PipelineRun`, `PipelineStatus`, `Stage`, `StageAttempt`, `StageStatus`, `WorkflowPhase`, `WorkflowDefinitionRecord`, `WorkflowStepConfig`

**Commands to move:** `StartWorkflow`

**Events to move:** `IntentRouted`, `WorkflowStarted`, `WorkflowAdvanced`, `PipelineRunStarted`, `PipelineStageCompleted`, `PipelineRunCompleted`, `PipelineRunFailed`, `PipelineRunCancelled`, `PipelineRunDeleted`, `PipelineStageApproved`, `PipelineStageRejected`, `PipelineStageRetried`, `StageReportEdited`, `StageReportRegenerated`, `WorkflowDefinitionCreated`, `WorkflowDefinitionUpdated`, `WorkflowDefinitionRemoved`

- [ ] **Steps:** Same pattern.

---

### Task 12: Move remaining domain types and events to `lintel-domain`

**Files:**
- Create: `packages/domain/src/lintel/domain/types.py`
- Create: `packages/domain/src/lintel/domain/events.py`

**Types to move:** Everything remaining in `contracts/types.py` except `ThreadRef`, `ActorType`, `CorrelationId`, `EventId`:
- `Project`, `ProjectStatus`, `WorkItem`, `WorkItemStatus`, `WorkItemType`
- `Tag`, `Board`, `BoardColumn`
- `ApprovalRequest`, `ApprovalStatus`
- `AuditEntry`, `AgentSession` (if not moved to agents)
- `User`, `UserRole`, `Team`
- `NotificationChannel`, `NotificationRule`
- `Policy`, `PolicyAction`
- `Environment`, `EnvironmentType`, `Variable`
- `Trigger`, `TriggerType`, `WorkflowHook`, `HookType`
- `AutomationDefinition`, `AutomationTriggerType`, `ConcurrencyPolicy`
- `CodeArtifact`, `TestVerdict`, `TestResult`
- `ResourceVersion`, `PassedConstraint`, `JobInput`
- `MCPServer`, `ChatSession`
- `DeliveryLoop`, `PhaseTransitionRecord`, `DEFAULT_DELIVERY_PHASES`
- All compliance types: `Regulation`, `CompliancePolicy`, `Procedure`, `Practice`, `Strategy`, `KPI`, `Experiment`, `ComplianceMetric`, `KnowledgeEntry`, `ArchitectureDecision`, `KnowledgeExtractionRun` + all related enums

**Events to move:** All remaining events in `contracts/events.py` — projects, work items, boards, tags, users, teams, approvals, notifications, settings, hooks, compliance, deployment, guardrails, delivery loop, etc.

- [ ] **Step 1:** Create `types.py` with all the above types
- [ ] **Step 2:** Create `events.py` with all remaining events + `register_events()` call
- [ ] **Step 3:** Update all imports across codebase (this is the largest find/replace)
- [ ] **Step 4:** Remove everything from contracts except the slim kernel
- [ ] **Step 5:** `make lint && make typecheck && make test-unit`
- [ ] **Step 6:** Commit

---

## Chunk 5: Cleanup and verification

### Task 13: Slim down contracts to kernel only

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/types.py` — only `ThreadRef`, `ActorType`, `CorrelationId`, `EventId`
- Modify: `packages/contracts/src/lintel/contracts/events.py` — only `EventEnvelope`, `EVENT_TYPE_MAP`, `register_events`, `deserialize_event`
- Modify: `packages/contracts/src/lintel/contracts/protocols.py` — only `EventHandler`, `EventBus`, `CommandDispatcher`, `EventStore`
- Delete: `packages/contracts/src/lintel/contracts/commands.py`
- Delete: `packages/contracts/src/lintel/contracts/data_models.py`
- Delete: `packages/contracts/src/lintel/contracts/errors.py`
- Delete: `packages/contracts/src/lintel/contracts/projections.py`
- Delete: `packages/contracts/src/lintel/contracts/stream_events.py`
- Modify: `packages/contracts/pyproject.toml` — remove `pydantic` dep if no longer needed

- [ ] **Step 1:** Verify contracts only contains the kernel types
- [ ] **Step 2:** `make lint && make typecheck && make test-unit`
- [ ] **Step 3:** Commit

---

### Task 14: Update pyproject.toml dependencies

**Files:**
- Modify: `packages/*/pyproject.toml` for all packages

Update dependency declarations so packages depend on the domain packages they actually import from, not just `lintel-contracts`:

- `lintel-agents` depends on: `lintel-contracts`, `lintel-sandbox` (for types)
- `lintel-workflows` depends on: `lintel-contracts`, `lintel-agents`, `lintel-sandbox`
- `lintel-models` depends on: `lintel-contracts`
- `lintel-persistence` depends on: `lintel-contracts`
- `lintel-domain` depends on: `lintel-contracts`, `lintel-agents`
- `lintel-app` depends on: all packages (already does)
- etc.

- [ ] **Step 1:** Update all `pyproject.toml` files
- [ ] **Step 2:** `uv sync --all-extras --all-packages`
- [ ] **Step 3:** `make lint && make typecheck && make test-unit`
- [ ] **Step 4:** Commit

---

### Task 15: Update affected-packages.sh dependency graph

**Files:**
- Modify: `scripts/affected-packages.sh`

Update the `DEPENDENTS` associative array to reflect the new dependency graph. For example, `lintel-sandbox` changes should now trigger `lintel-agents`, `lintel-workflows`, `lintel-app` — not everything.

- [ ] **Step 1:** Update the `DEPENDENTS` map
- [ ] **Step 2:** Verify with a dry run: `bash scripts/affected-packages.sh origin/main`
- [ ] **Step 3:** Commit

---

### Task 16: Update contracts tests

**Files:**
- Modify: `packages/contracts/tests/` — update or move tests that test moved types

Tests for sandbox protocols → `packages/sandbox/tests/`
Tests for projection protocols → `packages/projections/tests/`
etc.

- [ ] **Step 1:** Move/update contract tests
- [ ] **Step 2:** `make test-unit`
- [ ] **Step 3:** Commit

---

### Task 17: Update CLAUDE.md and docs

**Files:**
- Modify: `CLAUDE.md` — update Architecture section to reflect new package boundaries
- Modify: `docs/types-reference.md` — regenerate with `/update-types`

- [ ] **Step 1:** Update CLAUDE.md architecture description
- [ ] **Step 2:** Regenerate types reference
- [ ] **Step 3:** Commit

---

### Task 18: Final verification

- [ ] **Step 1:** `make all` (lint + typecheck + test + integration + UI build)
- [ ] **Step 2:** Verify `make test-affected` with a targeted change only triggers expected packages
- [ ] **Step 3:** Squash or organize commits, create PR
