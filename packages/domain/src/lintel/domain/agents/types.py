"""Agent prompt and memory domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class MemoryCategory(StrEnum):
    """Category of an agent memory entry."""

    CONTEXT = "context"
    PREFERENCE = "preference"
    LEARNED = "learned"


@dataclass(frozen=True)
class AgentPromptVersion:
    """An immutable snapshot of an agent's prompt text at a given version."""

    agent_id: str
    version: int
    prompt_text: str
    author: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AgentMemoryEntry:
    """A key-value memory entry scoped to an agent."""

    agent_id: str
    key: str
    value: str
    category: MemoryCategory = MemoryCategory.CONTEXT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
