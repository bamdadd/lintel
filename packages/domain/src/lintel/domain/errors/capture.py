"""Error capture engine for ingesting and grouping errors (REQ-F007)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import hashlib
from typing import Any
import uuid

from lintel.domain.errors.types import (
    CapturedError,
    ErrorGroup,
    ErrorGroupStatus,
    ErrorSeverity,
    ErrorSource,
)


def _fingerprint(error: CapturedError) -> str:
    """Compute a stable fingerprint from source + message + service."""
    key = f"{error.source}:{error.service}:{error.message}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class ErrorCaptureEngine:
    """Ingests error payloads and manages error groups."""

    def __init__(self) -> None:
        self._groups: dict[str, ErrorGroup] = {}

    def ingest(self, payload: dict[str, Any], source: ErrorSource) -> CapturedError:
        """Parse a raw payload dict into a CapturedError and add to groups."""
        now = datetime.now(tz=UTC)
        error = CapturedError(
            error_id=payload.get("error_id", uuid.uuid4().hex),
            source=source,
            severity=ErrorSeverity(payload.get("severity", "error")),
            message=payload.get("message", ""),
            stacktrace=payload.get("stacktrace", ""),
            service=payload.get("service", ""),
            environment=payload.get("environment", ""),
            first_seen=now,
            last_seen=now,
            occurrence_count=int(payload.get("occurrence_count", 1)),
            tags=tuple(payload.get("tags", ())),
            url=payload.get("url", ""),
        )
        fp = _fingerprint(error)
        existing = self._groups.get(fp)
        if existing is not None:
            self._groups[fp] = ErrorGroup(
                group_id=existing.group_id,
                fingerprint=fp,
                errors=(*existing.errors, error),
                status=existing.status,
            )
        else:
            self._groups[fp] = ErrorGroup(
                group_id=uuid.uuid4().hex,
                fingerprint=fp,
                errors=(error,),
            )
        return error

    def group_by_fingerprint(
        self,
        errors: list[CapturedError],
    ) -> list[ErrorGroup]:
        """Group a list of errors by their computed fingerprint."""
        buckets: dict[str, list[CapturedError]] = defaultdict(list)
        for err in errors:
            buckets[_fingerprint(err)].append(err)
        return [
            ErrorGroup(
                group_id=uuid.uuid4().hex,
                fingerprint=fp,
                errors=tuple(errs),
            )
            for fp, errs in buckets.items()
        ]

    def get_trending(self, timeframe: datetime) -> list[ErrorGroup]:
        """Return groups with errors after the given timeframe, sorted by count."""
        results: list[ErrorGroup] = []
        for group in self._groups.values():
            recent = tuple(
                e for e in group.errors if e.last_seen is not None and e.last_seen >= timeframe
            )
            if recent:
                results.append(
                    ErrorGroup(
                        group_id=group.group_id,
                        fingerprint=group.fingerprint,
                        errors=recent,
                        status=group.status,
                    )
                )
        return sorted(results, key=lambda g: len(g.errors), reverse=True)

    def acknowledge(self, group_id: str) -> None:
        """Mark a group as acknowledged."""
        self._update_status(group_id, ErrorGroupStatus.ACKNOWLEDGED)

    def resolve(self, group_id: str) -> None:
        """Mark a group as resolved."""
        self._update_status(group_id, ErrorGroupStatus.RESOLVED)

    def _update_status(self, group_id: str, status: ErrorGroupStatus) -> None:
        for fp, group in self._groups.items():
            if group.group_id == group_id:
                self._groups[fp] = ErrorGroup(
                    group_id=group.group_id,
                    fingerprint=group.fingerprint,
                    errors=group.errors,
                    status=status,
                )
                return
        msg = f"Error group {group_id} not found"
        raise KeyError(msg)
