"""Tests for error capture domain types."""

from lintel.domain.errors.types import (
    CapturedError,
    ErrorGroup,
    ErrorGroupStatus,
    ErrorSeverity,
    ErrorSource,
)


def test_error_source_values() -> None:
    assert ErrorSource.SENTRY == "sentry"
    assert ErrorSource.DATADOG == "datadog"
    assert ErrorSource.CLOUDWATCH == "cloudwatch"
    assert ErrorSource.CUSTOM == "custom"


def test_error_severity_values() -> None:
    assert ErrorSeverity.FATAL == "fatal"
    assert ErrorSeverity.ERROR == "error"
    assert ErrorSeverity.WARNING == "warning"
    assert ErrorSeverity.INFO == "info"


def test_captured_error_defaults() -> None:
    err = CapturedError(
        error_id="e1",
        source=ErrorSource.SENTRY,
        severity=ErrorSeverity.ERROR,
        message="Something broke",
    )
    assert err.stacktrace == ""
    assert err.service == ""
    assert err.occurrence_count == 1
    assert err.tags == ()


def test_error_group_defaults() -> None:
    group = ErrorGroup(group_id="g1", fingerprint="abc123")
    assert group.errors == ()
    assert group.status == ErrorGroupStatus.OPEN


def test_captured_error_frozen() -> None:
    err = CapturedError(
        error_id="e1",
        source=ErrorSource.DATADOG,
        severity=ErrorSeverity.WARNING,
        message="warn",
    )
    try:
        err.message = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised")
    except AttributeError:
        pass
