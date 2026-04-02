"""Continuous autonomous loop domain types (REQ-034.7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class LoopStatus(StrEnum):
    """Runtime status of an autonomous loop."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass(frozen=True)
class LoopConfig:
    """Configuration for a continuous autonomous loop."""

    loop_id: str
    project_id: str
    trigger_interval_seconds: int = 60
    max_iterations: int | None = None
    auto_pick_from_board: bool = True
    filters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LoopIteration:
    """Record of a single iteration within an autonomous loop."""

    iteration_number: int
    started_at: datetime
    completed_at: datetime | None = None
    work_item_id: str | None = None
    outcome: str = ""
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class AutonomousLoop:
    """Aggregate representing a continuous autonomous workflow loop."""

    loop_id: str
    config: LoopConfig
    status: LoopStatus = LoopStatus.IDLE
    iterations: tuple[LoopIteration, ...] = ()
    current_iteration: int = 0
