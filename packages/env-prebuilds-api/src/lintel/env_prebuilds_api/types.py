"""Environment prebuild domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class PrebuildStatus(StrEnum):
    """Status of a prebuild execution."""

    PENDING = "pending"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class PrebuildConfig:
    """Defines a prebuild specification for keeping agent environments warm."""

    config_id: str
    name: str
    environment_id: str
    image: str = ""
    setup_commands: list[str] = field(default_factory=list)
    warmup_count: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )


@dataclass(frozen=True)
class PrebuildRun:
    """Tracks a single prebuild execution."""

    run_id: str
    config_id: str
    status: PrebuildStatus = PrebuildStatus.PENDING
    started_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )
    finished_at: str | None = None
    error: str | None = None
