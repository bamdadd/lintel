"""Channel expansion domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


class ChannelType(Enum):
    """Supported communication channel types."""

    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    TEAMS = "teams"
    WEB = "web"
    EMAIL = "email"


@dataclass(frozen=True)
class ChannelMessage:
    """A message received from or sent to a communication channel."""

    channel_type: ChannelType
    channel_id: str
    sender_id: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration for a channel adapter instance."""

    channel_type: ChannelType
    channel_id: str
    credentials: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
