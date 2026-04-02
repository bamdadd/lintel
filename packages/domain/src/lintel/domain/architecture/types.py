"""Architecture decision types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ADRStatus(StrEnum):
    """Status of an architecture decision record."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class ArchitectureDecision:
    """An architecture decision record (ADR)."""

    adr_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: tuple[str, ...] = ()
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    superseded_by: str | None = None


@dataclass(frozen=True)
class ArchitectureLayer:
    """A named architecture layer grouping components, decisions, and constraints."""

    layer_name: str
    components: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
