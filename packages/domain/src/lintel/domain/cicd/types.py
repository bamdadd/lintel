"""CI/CD integration domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class CIProvider(StrEnum):
    """Supported CI/CD providers."""

    GITHUB_ACTIONS = "github_actions"
    CONCOURSE = "concourse"
    GENERIC_WEBHOOK = "generic_webhook"


class CIBuildStatus(StrEnum):
    """Normalized CI build status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CIBuild:
    """Normalized CI build representation across all providers."""

    build_id: str
    provider: CIProvider
    status: CIBuildStatus
    repo_url: str
    branch: str
    commit_sha: str
    pipeline_name: str = ""
    build_url: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CIWebhookPayload:
    """Raw webhook payload before normalization."""

    provider: CIProvider
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, object] = field(default_factory=dict)
