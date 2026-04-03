"""Release notes domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ReleaseEntry:
    """A single entry within a release note, typically from a merged PR."""

    pr_number: int
    title: str
    category: str
    description: str


@dataclass(frozen=True)
class ReleaseNote:
    """A set of release notes for a project version."""

    id: str
    project_id: str
    version: str
    title: str
    summary: str
    entries: tuple[ReleaseEntry, ...] = ()
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    published_at: str | None = None
