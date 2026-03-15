"""Core kernel types for Lintel. Immutable, no I/O dependencies.

This module provides only the fundamental types needed by the event envelope:
- ThreadRef: canonical workflow instance identifier
- ActorType: who performed an action
- CorrelationId / EventId: typed UUID wrappers

All other domain types live in their respective packages
(lintel.domain.types, lintel.workflows.types, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import NewType
from uuid import UUID

from lintel.contracts.channel_type import ChannelType


@dataclass(frozen=True)
class ThreadRef:
    """Canonical identifier for a workflow instance (channel thread).

    Supports multiple channel types via the channel_type field.
    Defaults to SLACK for backward compatibility.
    """

    workspace_id: str
    channel_id: str
    thread_ts: str
    channel_type: ChannelType = field(default=ChannelType.SLACK)

    @property
    def stream_id(self) -> str:
        return (
            f"thread:{self.channel_type.value}"
            f":{self.workspace_id}:{self.channel_id}:{self.thread_ts}"
        )

    def __str__(self) -> str:
        return self.stream_id

    @classmethod
    def parse_stream_id(cls, stream_id: str) -> ThreadRef:
        """Parse a stream_id string back into a ThreadRef.

        Handles both new format 'thread:{channel_type}:{ws}:{ch}:{ts}'
        and legacy format 'thread:{ws}:{ch}:{ts}' (assumes SLACK).
        """
        parts = stream_id.split(":")
        if len(parts) == 5:
            # New format: thread:channel_type:workspace:channel:thread_ts
            _, ct, ws, ch, ts = parts
            try:
                channel_type = ChannelType(ct)
            except ValueError:
                # Legacy: the second part might be workspace_id, not channel_type
                return cls(
                    workspace_id=ct,
                    channel_id=ws,
                    thread_ts=f"{ch}:{ts}",
                    channel_type=ChannelType.SLACK,
                )
            return cls(
                workspace_id=ws,
                channel_id=ch,
                thread_ts=ts,
                channel_type=channel_type,
            )
        if len(parts) == 4:
            # Legacy format: thread:workspace:channel:thread_ts
            _, ws, ch, ts = parts
            return cls(
                workspace_id=ws,
                channel_id=ch,
                thread_ts=ts,
                channel_type=ChannelType.SLACK,
            )
        msg = f"Cannot parse stream_id: {stream_id}"
        raise ValueError(msg)


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


CorrelationId = NewType("CorrelationId", UUID)
EventId = NewType("EventId", UUID)
