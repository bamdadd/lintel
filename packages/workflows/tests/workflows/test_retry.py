"""Tests for auto-retry and error classification (REQ-006)."""

from __future__ import annotations

import pytest

from lintel.workflows.nodes._retry import (
    classify_error,
    compute_backoff,
    should_retry,
    wait_backoff,
)
from lintel.workflows.types import ErrorCategory, RetryPolicy


class TestClassifyError:
    def test_empty_message_returns_unknown(self) -> None:
        assert classify_error("") == ErrorCategory.UNKNOWN

    def test_timeout_is_transient(self) -> None:
        assert classify_error("connection timed out") == ErrorCategory.TRANSIENT

    def test_rate_limit_is_transient(self) -> None:
        assert classify_error("rate limit exceeded (429)") == ErrorCategory.TRANSIENT

    def test_503_is_transient(self) -> None:
        assert classify_error("HTTP 503 Service Unavailable") == ErrorCategory.TRANSIENT

    def test_connection_refused_is_transient(self) -> None:
        assert classify_error("connection refused") == ErrorCategory.TRANSIENT

    def test_server_error_is_transient(self) -> None:
        assert classify_error("server unavailable") == ErrorCategory.TRANSIENT

    def test_oom_is_resource(self) -> None:
        assert classify_error("out of memory") == ErrorCategory.RESOURCE

    def test_disk_full_is_resource(self) -> None:
        assert classify_error("no space left on device") == ErrorCategory.RESOURCE

    def test_sandbox_failed_is_resource(self) -> None:
        assert classify_error("sandbox creation failed") == ErrorCategory.RESOURCE

    def test_container_exited_is_resource(self) -> None:
        assert classify_error("container exited with code 137") == ErrorCategory.RESOURCE

    def test_no_sandbox_available_is_resource(self) -> None:
        assert classify_error("No sandbox available in pool") == ErrorCategory.RESOURCE

    def test_validation_error_is_deterministic(self) -> None:
        assert classify_error("validation error: field X required") == ErrorCategory.DETERMINISTIC

    def test_permission_denied_is_deterministic(self) -> None:
        assert classify_error("permission denied") == ErrorCategory.DETERMINISTIC

    def test_not_found_is_deterministic(self) -> None:
        assert classify_error("resource not found") == ErrorCategory.DETERMINISTIC

    def test_403_is_deterministic(self) -> None:
        assert classify_error("HTTP 403 Forbidden") == ErrorCategory.DETERMINISTIC

    def test_unknown_error(self) -> None:
        assert classify_error("something completely unexpected happened") == ErrorCategory.UNKNOWN

    def test_sso_token_expiry_is_transient(self) -> None:
        msg = (
            "litellm.APIConnectionError: Error when retrieving token from sso: "
            "Token has expired and refresh failed"
        )
        assert classify_error(msg) == ErrorCategory.TRANSIENT

    def test_token_expired_is_transient(self) -> None:
        assert classify_error("token expired") == ErrorCategory.TRANSIENT

    def test_refresh_failed_is_transient(self) -> None:
        assert classify_error("refresh failed") == ErrorCategory.TRANSIENT

    def test_api_connection_error_is_transient(self) -> None:
        assert classify_error("APIConnectionError") == ErrorCategory.TRANSIENT

    def test_sso_token_expiry_not_deterministic(self) -> None:
        """SSO 'refresh failed' must NOT match the deterministic 'authentication failed' pattern."""
        msg = "Token has expired and refresh failed"
        assert classify_error(msg) != ErrorCategory.DETERMINISTIC

    def test_deterministic_takes_precedence_over_transient(self) -> None:
        # "not found" + "timeout" => deterministic wins (checked first)
        assert classify_error("not found after timeout") == ErrorCategory.DETERMINISTIC


class TestShouldRetry:
    def test_retries_transient_error(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert should_retry(policy, attempt=0, error_message="connection timed out")

    def test_retries_resource_error(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert should_retry(policy, attempt=0, error_message="out of memory")

    def test_does_not_retry_deterministic_error(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert not should_retry(policy, attempt=0, error_message="validation error")

    def test_does_not_retry_when_max_reached(self) -> None:
        policy = RetryPolicy(max_retries=2)
        assert not should_retry(policy, attempt=2, error_message="connection timed out")

    def test_does_not_retry_when_max_retries_zero(self) -> None:
        policy = RetryPolicy(max_retries=0)
        assert not should_retry(policy, attempt=0, error_message="connection timed out")

    def test_custom_retryable_categories(self) -> None:
        policy = RetryPolicy(
            max_retries=3,
            retryable_categories=(ErrorCategory.DETERMINISTIC,),
        )
        assert should_retry(policy, attempt=0, error_message="validation error")
        assert not should_retry(policy, attempt=0, error_message="connection timed out")

    def test_sso_token_expiry_retried_with_default_policy(self) -> None:
        policy = RetryPolicy()
        msg = (
            "litellm.APIConnectionError: Error when retrieving token from sso: "
            "Token has expired and refresh failed"
        )
        assert should_retry(policy, attempt=0, error_message=msg)

    def test_retries_sandbox_pool_exhausted(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert should_retry(policy, attempt=0, error_message="No sandbox available in pool")

    def test_unknown_error_not_retried_by_default(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert not should_retry(policy, attempt=0, error_message="weird unknown thing")


class TestComputeBackoff:
    def test_first_attempt(self) -> None:
        policy = RetryPolicy(backoff_seconds=5.0, backoff_multiplier=2.0)
        assert compute_backoff(policy, 0) == 5.0

    def test_second_attempt(self) -> None:
        policy = RetryPolicy(backoff_seconds=5.0, backoff_multiplier=2.0)
        assert compute_backoff(policy, 1) == 10.0

    def test_capped_at_max(self) -> None:
        policy = RetryPolicy(
            backoff_seconds=5.0,
            backoff_multiplier=10.0,
            max_backoff_seconds=30.0,
        )
        assert compute_backoff(policy, 2) == 30.0

    def test_third_attempt(self) -> None:
        policy = RetryPolicy(backoff_seconds=5.0, backoff_multiplier=2.0)
        assert compute_backoff(policy, 2) == 20.0


class TestWaitBackoff:
    async def test_wait_returns_delay(self) -> None:
        policy = RetryPolicy(backoff_seconds=0.01, backoff_multiplier=1.0)
        delay = await wait_backoff(policy, 0)
        assert delay == pytest.approx(0.01, abs=0.001)


class TestRetryPolicyDefaults:
    def test_default_values(self) -> None:
        policy = RetryPolicy()
        assert policy.max_retries == 2
        assert policy.backoff_seconds == 5.0
        assert policy.backoff_multiplier == 2.0
        assert policy.max_backoff_seconds == 120.0
        assert ErrorCategory.TRANSIENT in policy.retryable_categories
        assert ErrorCategory.RESOURCE in policy.retryable_categories


class TestRecoveryStrategyAndErrorCategory:
    def test_error_category_values(self) -> None:
        assert ErrorCategory.TRANSIENT == "transient"
        assert ErrorCategory.DETERMINISTIC == "deterministic"
        assert ErrorCategory.RESOURCE == "resource"
        assert ErrorCategory.UNKNOWN == "unknown"

    def test_recovery_strategy_values(self) -> None:
        from lintel.workflows.types import RecoveryStrategy

        assert RecoveryStrategy.RETRY == "retry"
        assert RecoveryStrategy.SKIP == "skip"
        assert RecoveryStrategy.FAIL_FAST == "fail_fast"
