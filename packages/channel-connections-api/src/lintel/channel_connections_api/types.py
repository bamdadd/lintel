"""Channel connection domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ChannelConnection:
    """A configured channel connection (e.g. Slack workspace, Telegram bot)."""

    id: str
    provider: str
    channel_id: str
    workspace_id: str
    config: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
