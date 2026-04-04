"""Automation domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AutomationTriggerType(StrEnum):
    CRON = "cron"
    EVENT = "event"
    MANUAL = "manual"


class ConcurrencyPolicy(StrEnum):
    ALLOW = "allow"
    QUEUE = "queue"
    SKIP = "skip"
    CANCEL = "cancel"


@dataclass(frozen=True)
class AutomationDefinition:
    """Server-side automation rule that executes workflows on schedule or event."""

    automation_id: str
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True
    max_chain_depth: int = 3
    created_at: str = ""
    updated_at: str = ""
