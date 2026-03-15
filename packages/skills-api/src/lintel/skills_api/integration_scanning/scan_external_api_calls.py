"""Scanner for external / third-party API call patterns."""

from __future__ import annotations

from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

# Well-known third-party SDK import patterns.
_SDK_SERVICES: list[tuple[str, re.Pattern[str]]] = [
    ("stripe", re.compile(r"^\s*(?:from\s+stripe|import\s+stripe)\b")),
    ("twilio", re.compile(r"^\s*(?:from\s+twilio|import\s+twilio)\b")),
    ("sendgrid", re.compile(r"^\s*(?:from\s+sendgrid|import\s+sendgrid)\b")),
    ("slack", re.compile(r"^\s*(?:from\s+slack_sdk|import\s+slack_sdk)\b")),
    ("slack", re.compile(r"\bWebClient\s*\(.*token")),
    ("aws_sdk", re.compile(r"^\s*(?:from\s+boto3|import\s+boto3)\b")),
    ("aws_sdk", re.compile(r"^\s*(?:from\s+botocore|import\s+botocore)\b")),
    ("gcp_sdk", re.compile(r"^\s*(?:from\s+google\.cloud|import\s+google\.cloud)\b")),
    ("azure_sdk", re.compile(r"^\s*(?:from\s+azure\.|import\s+azure\.)\b")),
    ("openai", re.compile(r"^\s*(?:from\s+openai|import\s+openai)\b")),
    ("anthropic", re.compile(r"^\s*(?:from\s+anthropic|import\s+anthropic)\b")),
    ("pagerduty", re.compile(r"^\s*(?:from\s+pdpyras|import\s+pdpyras)\b")),
    ("datadog", re.compile(r"^\s*(?:from\s+datadog|import\s+datadog)\b")),
    ("sentry", re.compile(r"^\s*(?:from\s+sentry_sdk|import\s+sentry_sdk)\b")),
]

# OpenAPI generated client usage patterns.
_OPENAPI_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bApiClient\s*\("),
    re.compile(r"\bConfiguration\s*\(\s*host\s*="),
    re.compile(r"^\s*from\s+\w+_client\b"),
]

# Generic HTTP calls with external URLs.
_EXTERNAL_URL_PATTERN = re.compile(
    r"""(?:requests|httpx|aiohttp)\.\w+\s*\(\s*['"]https?://[^'"]+['"]"""
)


async def scan_external_api_calls(file_paths: list[str]) -> list[dict]:
    """Scan Python files for external / third-party API call patterns.

    Detects third-party SDK imports (stripe, twilio, sendgrid, slack_sdk, etc.),
    OpenAPI generated client usage, and generic HTTP calls with external URLs.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of dicts with keys: source_file, service_name,
        sdk_pattern, line_number, match_text.
    """
    results: list[dict] = []

    for file_path_str in file_paths:
        path = Path(file_path_str)
        if not path.exists():
            logger.warning("file_not_found", path=file_path_str)
            continue
        if path.suffix != ".py":
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("file_read_error", path=file_path_str, error=str(exc))
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            # Third-party SDK imports
            for service_name, pattern in _SDK_SERVICES:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "service_name": service_name,
                            "sdk_pattern": "sdk_import",
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

            # OpenAPI generated clients
            for pattern in _OPENAPI_PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "service_name": "openapi_generated",
                            "sdk_pattern": "openapi_client",
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

            # Generic HTTP with external URLs
            match = _EXTERNAL_URL_PATTERN.search(line)
            if match:
                results.append(
                    {
                        "source_file": file_path_str,
                        "service_name": "external_http",
                        "sdk_pattern": "http_url",
                        "line_number": line_number,
                        "match_text": match.group(0).strip(),
                    }
                )

    logger.info("scan_external_api_calls_complete", total_matches=len(results))
    return results
