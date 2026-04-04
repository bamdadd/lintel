"""In-memory stores for proactive triggers and execution history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class EventPattern(StrEnum):
    """Supported event patterns that can auto-launch an agent."""

    COMMIT_PUSHED = "commit_pushed"
    PR_OPENED = "pr_opened"
    PR_MERGED = "pr_merged"
    PIPELINE_FAILED = "pipeline_failed"
    SCHEDULE = "schedule"
    WORK_ITEM_CREATED = "work_item_created"
    DRIFT_DETECTED = "drift_detected"


class ExecutionStatus(StrEnum):
    """Status of a proactive trigger execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProactiveTrigger:
    """A rule that auto-launches an agent when an event pattern matches."""

    trigger_id: str
    name: str
    event_pattern: str
    agent_definition_id: str
    project_id: str
    config: dict[str, object] | None = None
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class TriggerExecution:
    """Record of a proactive trigger firing."""

    execution_id: str
    trigger_id: str
    event_payload: dict[str, object]
    status: str = ExecutionStatus.PENDING
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    result: dict[str, object] | None = None


class InMemoryProactiveTriggerStore:
    """In-memory store for proactive trigger definitions."""

    def __init__(self) -> None:
        self._triggers: dict[str, ProactiveTrigger] = {}

    async def add(self, trigger: ProactiveTrigger) -> None:
        self._triggers[trigger.trigger_id] = trigger

    async def get(self, trigger_id: str) -> ProactiveTrigger | None:
        return self._triggers.get(trigger_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[ProactiveTrigger]:
        items = list(self._triggers.values())
        if project_id is not None:
            items = [t for t in items if t.project_id == project_id]
        return items

    async def remove(self, trigger_id: str) -> None:
        self._triggers.pop(trigger_id, None)


class InMemoryTriggerExecutionStore:
    """In-memory store for trigger execution history."""

    def __init__(self) -> None:
        self._executions: dict[str, TriggerExecution] = {}

    async def add(self, execution: TriggerExecution) -> None:
        self._executions[execution.execution_id] = execution

    async def get(self, execution_id: str) -> TriggerExecution | None:
        return self._executions.get(execution_id)

    async def list_all(
        self,
        trigger_id: str | None = None,
    ) -> list[TriggerExecution]:
        items = list(self._executions.values())
        if trigger_id is not None:
            items = [e for e in items if e.trigger_id == trigger_id]
        return sorted(items, key=lambda e: e.started_at, reverse=True)
