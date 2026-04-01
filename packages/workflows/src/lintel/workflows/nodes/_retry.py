"""Auto-retry and error classification for self-healing workflows.

Classifies errors into categories (transient, deterministic, resource, unknown)
and computes whether a failed step should be automatically retried based on
the configured ``RetryPolicy``.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.workflows.types import ErrorCategory, RetryPolicy

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Error classification patterns
# ---------------------------------------------------------------------------

_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"timed?\s*out", re.IGNORECASE),
    re.compile(r"rate.?limit", re.IGNORECASE),
    re.compile(r"429"),
    re.compile(r"503"),
    re.compile(r"502"),
    re.compile(r"connection\s*(refused|reset|aborted)", re.IGNORECASE),
    re.compile(r"temporary\s*failure", re.IGNORECASE),
    re.compile(r"ECONNREFUSED|ECONNRESET|ETIMEDOUT", re.IGNORECASE),
    re.compile(r"server\s*(error|unavailable)", re.IGNORECASE),
    re.compile(r"retry.?after", re.IGNORECASE),
)

_RESOURCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"out\s*of\s*memory", re.IGNORECASE),
    re.compile(r"OOM", re.IGNORECASE),
    re.compile(r"no\s*space\s*left", re.IGNORECASE),
    re.compile(r"disk\s*full", re.IGNORECASE),
    re.compile(r"sandbox.*failed", re.IGNORECASE),
    re.compile(r"container.*exited", re.IGNORECASE),
    re.compile(r"memory\s*limit", re.IGNORECASE),
)

_DETERMINISTIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"validation\s*error", re.IGNORECASE),
    re.compile(r"invalid\s*(input|argument|parameter)", re.IGNORECASE),
    re.compile(r"permission\s*denied", re.IGNORECASE),
    re.compile(r"not\s*found", re.IGNORECASE),
    re.compile(r"401|403|404"),
    re.compile(r"authentication\s*failed", re.IGNORECASE),
    re.compile(r"missing\s*required", re.IGNORECASE),
)


def classify_error(error_message: str) -> ErrorCategory:
    """Classify an error message into a recovery category.

    The classifier checks patterns in order of specificity:
    deterministic > transient > resource > unknown.
    """
    from lintel.workflows.types import ErrorCategory

    if not error_message:
        return ErrorCategory.UNKNOWN

    for pattern in _DETERMINISTIC_PATTERNS:
        if pattern.search(error_message):
            return ErrorCategory.DETERMINISTIC

    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(error_message):
            return ErrorCategory.TRANSIENT

    for pattern in _RESOURCE_PATTERNS:
        if pattern.search(error_message):
            return ErrorCategory.RESOURCE

    return ErrorCategory.UNKNOWN


def should_retry(
    policy: RetryPolicy,
    attempt: int,
    error_message: str,
) -> bool:
    """Determine whether a step should be retried.

    Args:
        policy: The retry policy for this step.
        attempt: The current attempt number (1-based, i.e. first failure = attempt 1).
        error_message: The error string from the failed step.

    Returns:
        True if the step should be retried.
    """
    if attempt >= policy.max_retries:
        return False

    category = classify_error(error_message)
    return category in policy.retryable_categories


def compute_backoff(policy: RetryPolicy, attempt: int) -> float:
    """Compute the backoff delay in seconds for a given attempt number.

    Uses exponential backoff capped at ``max_backoff_seconds``.
    """
    delay = policy.backoff_seconds * (policy.backoff_multiplier**attempt)
    return min(delay, policy.max_backoff_seconds)


async def wait_backoff(policy: RetryPolicy, attempt: int) -> float:
    """Sleep for the computed backoff duration and return the delay used."""
    delay = compute_backoff(policy, attempt)
    logger.info("retry_backoff", delay_seconds=delay, attempt=attempt)
    await asyncio.sleep(delay)
    return delay
