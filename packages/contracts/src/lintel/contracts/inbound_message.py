"""InboundMessage envelope — normalizes events from any channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.channel_type import ChannelType


@dataclass(frozen=True)
class InboundMessage:
    """Channel-agnostic inbound message envelope.

    All channel adapters translate their native event format into this
    common structure before handing off to the coordination layer.
    """

    channel_type: ChannelType
    channel_id: str
    thread_id: str
    sender_id: str
    text: str
    raw_payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    workspace_id: str = ""
