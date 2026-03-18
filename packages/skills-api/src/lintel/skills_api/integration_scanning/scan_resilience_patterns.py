"""Scanner for resilience patterns: retries, circuit breakers, timeouts, bulkheads."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

# --- Retry patterns -----------------------------------------------------------

_RETRY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # tenacity
    ("tenacity", re.compile(r"@retry\b")),
    ("tenacity", re.compile(r"@retry_if_\w+")),
    ("tenacity", re.compile(r"\bretrying\s*\(")),
    ("tenacity", re.compile(r"^\s*(?:from\s+tenacity|import\s+tenacity)\b")),
    # backoff
    ("backoff", re.compile(r"@backoff\.\w+")),
    ("backoff", re.compile(r"^\s*(?:from\s+backoff|import\s+backoff)\b")),
    # urllib3 Retry
    ("urllib3_retry", re.compile(r"\bRetry\s*\(.*total\s*=")),
    ("urllib3_retry", re.compile(r"^\s*from\s+urllib3\.util\.retry\s+import\s+Retry\b")),
    # stamina
    ("stamina", re.compile(r"@stamina\.retry\b")),
    ("stamina", re.compile(r"^\s*(?:from\s+stamina|import\s+stamina)\b")),
    # httpx retry (via transport)
    ("httpx_retry", re.compile(r"\bAsyncHTTPTransport\s*\(.*retries\s*=")),
    ("httpx_retry", re.compile(r"\bHTTPTransport\s*\(.*retries\s*=")),
    # Manual retry loops
    ("manual_retry", re.compile(r"for\s+\w+\s+in\s+range\s*\(.*retry", re.IGNORECASE)),
]

# --- Circuit breaker patterns -------------------------------------------------

_CIRCUIT_BREAKER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # pybreaker
    ("pybreaker", re.compile(r"\bCircuitBreaker\s*\(")),
    ("pybreaker", re.compile(r"@\w*circuit\w*", re.IGNORECASE)),
    ("pybreaker", re.compile(r"^\s*(?:from\s+pybreaker|import\s+pybreaker)\b")),
    # circuitbreaker
    ("circuitbreaker", re.compile(r"@circuit\b")),
    ("circuitbreaker", re.compile(r"^\s*(?:from\s+circuitbreaker|import\s+circuitbreaker)\b")),
    # resilience4j style (via aiobreaker etc.)
    ("aiobreaker", re.compile(r"^\s*(?:from\s+aiobreaker|import\s+aiobreaker)\b")),
]

# --- Timeout patterns ---------------------------------------------------------

_TIMEOUT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # httpx timeout
    ("httpx_timeout", re.compile(r"\bhttpx\.\w+\s*\(.*timeout\s*=", re.IGNORECASE)),
    ("httpx_timeout", re.compile(r"\bTimeout\s*\(\s*\d")),
    # requests timeout
    ("requests_timeout", re.compile(r"\brequests\.(get|post|put|delete|patch)\s*\(.*timeout\s*=")),
    # aiohttp timeout
    ("aiohttp_timeout", re.compile(r"\bClientTimeout\s*\(")),
    ("aiohttp_timeout", re.compile(r"\baiohttp\.ClientSession\s*\(.*timeout\s*=")),
    # asyncio timeout
    ("asyncio_timeout", re.compile(r"\basyncio\.wait_for\s*\(")),
    ("asyncio_timeout", re.compile(r"\basyncio\.timeout\s*\(")),
    ("asyncio_timeout", re.compile(r"^\s*(?:from\s+async_timeout|import\s+async_timeout)\b")),
    # gRPC timeout
    ("grpc_timeout", re.compile(r"\.with_call\s*\(.*timeout\s*=")),
    ("grpc_timeout", re.compile(r"\btimeout\s*=.*grpc", re.IGNORECASE)),
    # Generic timeout kwarg on common calls
    ("generic_timeout", re.compile(r"\.(execute|query|fetch|send)\s*\(.*timeout\s*=")),
]

# --- Bulkhead / rate limiting patterns ----------------------------------------

_BULKHEAD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("semaphore", re.compile(r"\basyncio\.Semaphore\s*\(")),
    ("semaphore", re.compile(r"\bthreading\.Semaphore\s*\(")),
    ("rate_limit", re.compile(r"^\s*(?:from\s+ratelimit|import\s+ratelimit)\b")),
    ("rate_limit", re.compile(r"@(rate_limit|limits)\b")),
    ("connection_pool", re.compile(r"\bcreate_pool\s*\(.*min_size\s*=")),
    ("connection_pool", re.compile(r"\bPoolManager\s*\(")),
    ("connection_pool", re.compile(r"\bpool_connections\s*=")),
    ("connection_pool", re.compile(r"\bmax_connections\s*=")),
]


async def scan_resilience_patterns(file_paths: list[str]) -> list[dict]:
    """Scan Python files for resilience patterns.

    Detects retry decorators/wrappers, circuit breakers, timeout configuration,
    and bulkhead/rate-limiting patterns.

    Returns:
        List of dicts with keys: source_file, resilience_type, pattern_family,
        line_number, match_text.
    """
    results: list[dict] = []

    for file_path_str in file_paths:
        path = Path(file_path_str)
        if not path.exists() or path.suffix != ".py":
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            for family, pattern in _RETRY_PATTERNS:
                if pattern.search(line):
                    results.append(
                        {
                            "source_file": file_path_str,
                            "resilience_type": "retry",
                            "pattern_family": family,
                            "line_number": line_number,
                            "match_text": line.strip()[:120],
                        }
                    )

            for family, pattern in _CIRCUIT_BREAKER_PATTERNS:
                if pattern.search(line):
                    results.append(
                        {
                            "source_file": file_path_str,
                            "resilience_type": "circuit_breaker",
                            "pattern_family": family,
                            "line_number": line_number,
                            "match_text": line.strip()[:120],
                        }
                    )

            for family, pattern in _TIMEOUT_PATTERNS:
                if pattern.search(line):
                    results.append(
                        {
                            "source_file": file_path_str,
                            "resilience_type": "timeout",
                            "pattern_family": family,
                            "line_number": line_number,
                            "match_text": line.strip()[:120],
                        }
                    )

            for family, pattern in _BULKHEAD_PATTERNS:
                if pattern.search(line):
                    results.append(
                        {
                            "source_file": file_path_str,
                            "resilience_type": "bulkhead",
                            "pattern_family": family,
                            "line_number": line_number,
                            "match_text": line.strip()[:120],
                        }
                    )

    logger.info("scan_resilience_patterns_complete", total_matches=len(results))
    return results


def build_file_resilience_index(
    resilience_results: list[dict],
) -> dict[str, dict[str, bool]]:
    """Build a per-file index of resilience capabilities.

    Returns:
        Dict mapping source_file → {has_retry, has_circuit_breaker, has_timeout,
        has_bulkhead}.
    """
    index: dict[str, dict[str, bool]] = defaultdict(
        lambda: {
            "has_retry": False,
            "has_circuit_breaker": False,
            "has_timeout": False,
            "has_bulkhead": False,
        }
    )

    type_key_map = {
        "retry": "has_retry",
        "circuit_breaker": "has_circuit_breaker",
        "timeout": "has_timeout",
        "bulkhead": "has_bulkhead",
    }

    for result in resilience_results:
        source = result.get("source_file", "")
        rtype = result.get("resilience_type", "")
        key = type_key_map.get(rtype)
        if key and source:
            index[source][key] = True

    return dict(index)
