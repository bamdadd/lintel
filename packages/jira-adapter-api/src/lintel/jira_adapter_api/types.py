"""Jira adapter types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SyncDirection(StrEnum):
    """Direction of a sync operation."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(StrEnum):
    """Status of a sync operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class JiraConnection:
    """Persisted Jira connection configuration."""

    connection_id: str
    project_id: str
    jira_base_url: str
    jira_project_key: str
    jira_email: str
    api_token: str  # stored encrypted at rest
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    status_mapping: dict[str, str] = field(default_factory=dict)
    created_at: str = ""


@dataclass(frozen=True)
class SyncRecord:
    """Record of a sync execution."""

    sync_id: str
    connection_id: str
    direction: SyncDirection
    status: SyncStatus = SyncStatus.PENDING
    items_synced: int = 0
    errors: tuple[str, ...] = ()
    started_at: str = ""
    finished_at: str = ""


@dataclass(frozen=True)
class JiraIssue:
    """Minimal representation of a Jira issue for mapping."""

    key: str
    summary: str
    status: str
    issue_type: str
    description: str = ""
    assignee: str | None = None
    updated: str = ""
