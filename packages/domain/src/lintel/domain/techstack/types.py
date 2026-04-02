"""Tech stack domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TechStackCategory(StrEnum):
    """Category of a tech stack component."""

    LANGUAGE = "language"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    TOOL = "tool"
    DATABASE = "database"
    SERVICE = "service"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class TechStackEntry:
    """A single discovered technology in a project's stack."""

    name: str
    version: str
    category: TechStackCategory
    source_file: str
    confidence: float  # 0.0 - 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            raise ValueError(msg)


@dataclass(frozen=True)
class TechStackReport:
    """Aggregated tech stack report with deduplication."""

    entries: tuple[TechStackEntry, ...] = ()
    source_files: tuple[str, ...] = ()

    @staticmethod
    def from_entries(entries: list[TechStackEntry]) -> TechStackReport:
        """Build a report from a list of entries, deduplicating by name+category.

        When duplicates exist, the entry with the highest confidence wins.
        """
        seen: dict[tuple[str, TechStackCategory], TechStackEntry] = {}
        source_files: set[str] = set()

        for entry in entries:
            key = (entry.name.lower(), entry.category)
            source_files.add(entry.source_file)
            existing = seen.get(key)
            if existing is None or entry.confidence > existing.confidence:
                seen[key] = entry

        deduped = sorted(seen.values(), key=lambda e: (e.category, e.name.lower()))
        return TechStackReport(
            entries=tuple(deduped),
            source_files=tuple(sorted(source_files)),
        )
