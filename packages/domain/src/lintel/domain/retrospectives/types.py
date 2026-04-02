"""Automated retrospectives domain types (DL-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class RetroStatus(StrEnum):
    """Lifecycle status of a retrospective."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ActionItemStatus(StrEnum):
    """Status of a retrospective action item."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass(frozen=True)
class Observation:
    """A single observation extracted from workflow run analysis."""

    observation_id: str = field(default_factory=lambda: str(uuid4()))
    category: str = ""
    description: str = ""
    severity: str = "info"
    source_run_id: str = ""


@dataclass(frozen=True)
class ActionItem:
    """An action item derived from retrospective observations."""

    action_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    owner: str = ""
    status: ActionItemStatus = ActionItemStatus.OPEN
    due_date: datetime | None = None
    created_from_observation: str = ""


@dataclass(frozen=True)
class Retrospective:
    """An automated retrospective covering a project over a time period."""

    retro_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = field(default_factory=lambda: datetime.now(UTC))
    observations: tuple[Observation, ...] = ()
    action_items: tuple[ActionItem, ...] = ()
    status: RetroStatus = RetroStatus.PENDING
    summary: str = ""
