"""Incident and error capture domain model (REQ-F007)."""

from lintel.domain.errors.capture import ErrorCaptureEngine
from lintel.domain.errors.types import (
    CapturedError,
    ErrorGroup,
    ErrorGroupStatus,
    ErrorSeverity,
    ErrorSource,
)

__all__ = [
    "CapturedError",
    "ErrorCaptureEngine",
    "ErrorGroup",
    "ErrorGroupStatus",
    "ErrorSeverity",
    "ErrorSource",
]
