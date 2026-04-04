"""Channel adapter registry domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ChannelAdapter:
    """A registered channel adapter keyed by bot_id + connection_id."""

    id: str
    bot_id: str
    connection_id: str
    channel_type: str  # "slack", "telegram", etc.
    adapter_class: str = ""  # fully-qualified class name
    config: dict[str, object] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0  # higher = preferred when routing
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
