"""Core kernel types for Lintel. Immutable, no I/O dependencies.

This module provides only the fundamental types needed by the event envelope:
- ThreadRef: canonical workflow instance identifier
- ActorType: who performed an action
- CorrelationId / EventId: typed UUID wrappers

All other domain types live in their respective packages
(lintel.domain.types, lintel.workflows.types, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType
from uuid import UUID


@dataclass(frozen=True)
class ThreadRef:
    """Canonical identifier for a workflow instance (Slack thread)."""

    workspace_id: str
    channel_id: str
    thread_ts: str

    @property
    def stream_id(self) -> str:
        return f"thread:{self.workspace_id}:{self.channel_id}:{self.thread_ts}"

    def __str__(self) -> str:
        return self.stream_id


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


CorrelationId = NewType("CorrelationId", UUID)
EventId = NewType("EventId", UUID)
