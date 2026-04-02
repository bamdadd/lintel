"""Domain types for the research knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class EdgeRelationship(StrEnum):
    """How a child research node relates to its parent."""

    EXTENDS = "extends"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"


@dataclass(frozen=True)
class ResearchNode:
    """A single research finding within the knowledge DAG."""

    id: str
    topic: str
    findings: tuple[str, ...] = ()
    confidence: float = 0.0
    source_run_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ResearchEdge:
    """A directed edge between two research nodes."""

    parent_id: str
    child_id: str
    relationship: EdgeRelationship = EdgeRelationship.SUPPORTS
