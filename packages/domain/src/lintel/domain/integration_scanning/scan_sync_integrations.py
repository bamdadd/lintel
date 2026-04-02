"""Scanner for synchronous integration patterns in Python source files."""

from __future__ import annotations

from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    # requests library
    ("requests", "http", re.compile(r"\brequests\.(get|post|put|delete|patch)\s*\(")),
    # httpx sync/async clients
    ("httpx", "http", re.compile(r"\bhttpx\.(Client|AsyncClient)\s*\(")),
    # aiohttp client session
    ("aiohttp", "http", re.compile(r"\baiohttp\.ClientSession\s*\(")),
    # gRPC imports
    ("grpc", "grpc", re.compile(r"^\s*(?:from\s+grpc|import\s+grpc)\b")),
    # graphql-core imports
    ("graphql-core", "graphql", re.compile(r"^\s*(?:from\s+graphql|import\s+graphql)\b")),
]


async def scan_sync_integrations(file_paths: list[str]) -> list[dict]:
    """Scan Python files for synchronous integration patterns.

    Detects usage of requests, httpx, aiohttp, gRPC, and graphql-core.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of dicts with keys: source_file, target_service_hint,
        protocol, line_number, match_text.
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
            for target_service_hint, protocol, pattern in _PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "target_service_hint": target_service_hint,
                            "protocol": protocol,
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

    logger.info("scan_sync_integrations_complete", total_matches=len(results))
    return results
