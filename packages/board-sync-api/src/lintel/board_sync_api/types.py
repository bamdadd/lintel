"""Board sync domain types."""

from __future__ import annotations

from enum import StrEnum


class SyncDirection(StrEnum):
    """Direction of synchronisation between Lintel and external system."""

    PULL = "pull"
    PUSH = "push"
    BIDIRECTIONAL = "bidirectional"


class SyncProvider(StrEnum):
    """Supported external board providers."""

    JIRA = "jira"
    NOTION = "notion"


class SyncStatus(StrEnum):
    """Current status of a sync integration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"


class ConflictStrategy(StrEnum):
    """How to resolve bidirectional conflicts."""

    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"
