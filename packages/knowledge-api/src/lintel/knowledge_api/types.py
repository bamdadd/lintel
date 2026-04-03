"""Knowledge base types for RAG project context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceType(StrEnum):
    """Source type for a knowledge entry."""

    DOCUMENT = "document"
    CODE = "code"
    URL = "url"
    NOTE = "note"


@dataclass(frozen=True)
class KnowledgeEntry:
    """A knowledge entry providing project context for agents."""

    id: str
    project_id: str
    title: str
    content: str = ""
    source_type: SourceType = SourceType.NOTE
    embedding: tuple[float, ...] | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
