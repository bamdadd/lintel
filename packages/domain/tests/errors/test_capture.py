"""Tests for ErrorCaptureEngine."""

from datetime import UTC, datetime, timedelta

from lintel.domain.errors.capture import ErrorCaptureEngine
from lintel.domain.errors.types import (
    CapturedError,
    ErrorGroupStatus,
    ErrorSeverity,
    ErrorSource,
)


def _make_engine_with_error() -> tuple[ErrorCaptureEngine, CapturedError]:
    engine = ErrorCaptureEngine()
    error = engine.ingest(
        {"message": "NullPointerException", "service": "api", "severity": "error"},
        ErrorSource.SENTRY,
    )
    return engine, error


def test_ingest_creates_captured_error() -> None:
    engine = ErrorCaptureEngine()
    error = engine.ingest(
        {"message": "timeout", "service": "worker", "tags": ["prod", "urgent"]},
        ErrorSource.DATADOG,
    )
    assert error.source == ErrorSource.DATADOG
    assert error.message == "timeout"
    assert error.tags == ("prod", "urgent")
    assert error.first_seen is not None


def test_ingest_groups_same_fingerprint() -> None:
    engine = ErrorCaptureEngine()
    engine.ingest({"message": "err", "service": "svc"}, ErrorSource.SENTRY)
    engine.ingest({"message": "err", "service": "svc"}, ErrorSource.SENTRY)
    # Internal groups should have 1 entry with 2 errors
    internal = list(engine._groups.values())
    assert len(internal) == 1
    assert len(internal[0].errors) == 2


def test_group_by_fingerprint() -> None:
    engine = ErrorCaptureEngine()
    e1 = CapturedError(
        error_id="1",
        source=ErrorSource.SENTRY,
        severity=ErrorSeverity.ERROR,
        message="err",
        service="svc",
    )
    e2 = CapturedError(
        error_id="2",
        source=ErrorSource.SENTRY,
        severity=ErrorSeverity.ERROR,
        message="err",
        service="svc",
    )
    e3 = CapturedError(
        error_id="3",
        source=ErrorSource.DATADOG,
        severity=ErrorSeverity.WARNING,
        message="other",
        service="other",
    )
    groups = engine.group_by_fingerprint([e1, e2, e3])
    assert len(groups) == 2
    sizes = sorted(len(g.errors) for g in groups)
    assert sizes == [1, 2]


def test_get_trending() -> None:
    engine, _ = _make_engine_with_error()
    old = datetime.now(tz=UTC) - timedelta(hours=1)
    trending = engine.get_trending(old)
    assert len(trending) == 1


def test_get_trending_filters_old() -> None:
    engine, _ = _make_engine_with_error()
    future = datetime.now(tz=UTC) + timedelta(hours=1)
    trending = engine.get_trending(future)
    assert len(trending) == 0


def test_acknowledge() -> None:
    engine, _ = _make_engine_with_error()
    group = next(iter(engine._groups.values()))
    engine.acknowledge(group.group_id)
    updated = engine._groups[group.fingerprint]
    assert updated.status == ErrorGroupStatus.ACKNOWLEDGED


def test_resolve() -> None:
    engine, _ = _make_engine_with_error()
    group = next(iter(engine._groups.values()))
    engine.resolve(group.group_id)
    updated = engine._groups[group.fingerprint]
    assert updated.status == ErrorGroupStatus.RESOLVED


def test_acknowledge_unknown_raises() -> None:
    engine = ErrorCaptureEngine()
    try:
        engine.acknowledge("nonexistent")
        raise AssertionError("Should have raised")
    except KeyError:
        pass
