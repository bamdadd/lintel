"""Domain types for incident and error capture (REQ-F007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class ErrorSource(StrEnum):
    """Origin platform for a captured error."""

    SENTRY = "sentry"
    DATADOG = "datadog"
    CLOUDWATCH = "cloudwatch"
    CUSTOM = "custom"


class ErrorSeverity(StrEnum):
    """Severity level of a captured error."""

    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorGroupStatus(StrEnum):
    """Lifecycle status of an error group."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class CapturedError:
    """A single error event ingested from a monitoring platform."""

    error_id: str
    source: ErrorSource
    severity: ErrorSeverity
    message: str
    stacktrace: str = ""
    service: str = ""
    environment: str = ""
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    occurrence_count: int = 1
    tags: tuple[str, ...] = ()
    url: str = ""


@dataclass(frozen=True)
class ErrorGroup:
    """A group of errors sharing the same fingerprint."""

    group_id: str
    fingerprint: str
    errors: tuple[CapturedError, ...] = ()
    status: ErrorGroupStatus = ErrorGroupStatus.OPEN
    tags: tuple[str, ...] = field(default_factory=tuple)
