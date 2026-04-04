"""Bot runtime types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class BotConnectionState(StrEnum):
    """Runtime state of a bot connection."""

    STOPPED = "stopped"
    STARTING = "starting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class BotHealth:
    """Health snapshot for a single bot connection."""

    bot_id: str
    state: BotConnectionState = BotConnectionState.STOPPED
    last_heartbeat: str = ""
    error: str = ""
    reconnect_attempts: int = 0
    started_at: str = ""

    def touch(self) -> None:
        """Update the heartbeat timestamp."""
        self.last_heartbeat = datetime.now(tz=UTC).isoformat()

    def mark_connected(self) -> None:
        self.state = BotConnectionState.CONNECTED
        self.error = ""
        self.reconnect_attempts = 0
        self.started_at = datetime.now(tz=UTC).isoformat()
        self.touch()

    def mark_failed(self, error: str) -> None:
        self.state = BotConnectionState.FAILED
        self.error = error
        self.touch()

    def mark_reconnecting(self) -> None:
        self.state = BotConnectionState.RECONNECTING
        self.reconnect_attempts += 1
        self.touch()


@dataclass
class _ManagedBot:
    """Internal bookkeeping for a running bot connection."""

    bot_id: str
    platform: str
    health: BotHealth = field(default_factory=lambda: BotHealth(bot_id=""))
    cancel: object | None = None  # asyncio.Task reference

    def __post_init__(self) -> None:
        if self.health.bot_id == "":
            self.health = BotHealth(bot_id=self.bot_id)
