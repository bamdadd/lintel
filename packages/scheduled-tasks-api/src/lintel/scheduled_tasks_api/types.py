"""Scheduled task domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class TaskType(StrEnum):
    DEPENDENCY_UPDATE = "dependency_update"
    COVERAGE_SWEEP = "coverage_sweep"
    SECURITY_SCAN = "security_scan"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ScheduledTask:
    """A cron-scheduled agent task."""

    id: str
    project_id: str
    name: str
    cron_expression: str
    task_type: TaskType
    description: str = ""
    config: dict[str, object] = field(default_factory=dict)
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
