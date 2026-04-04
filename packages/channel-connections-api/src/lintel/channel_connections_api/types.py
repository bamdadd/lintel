"""Channel connection domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ChannelConnection:
    """A configured channel connection (e.g. Slack workspace, Telegram bot)."""

    id: str
    channel_type: str  # "slack", "telegram", etc.
    credential_ref: str = ""  # reference to credential store entry
    workspace_id: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    allowed_workflows: tuple[str, ...] = ()
    allowed_agent_roles: tuple[str, ...] = ()
    project_ids: tuple[str, ...] = ()
    team_id: str = ""
    org_id: str = ""
    enabled: bool = True
    bot_username: str = ""
    webhook_url: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
