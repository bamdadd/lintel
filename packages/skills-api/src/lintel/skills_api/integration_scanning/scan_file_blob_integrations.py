"""Scanner for file and blob storage integration patterns."""

from __future__ import annotations

from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    # AWS S3 via boto3
    ("s3", "client", re.compile(r"\bboto3\.client\s*\(\s*['\"]s3['\"]\s*\)")),
    ("s3", "resource", re.compile(r"\bboto3\.resource\s*\(\s*['\"]s3['\"]\s*\)")),
    ("s3", "import", re.compile(r"^\s*(?:from\s+boto3|import\s+boto3)\b")),
    # Azure Blob Storage
    (
        "azure_blob",
        "import",
        re.compile(r"^\s*(?:from\s+azure\.storage\.blob|import\s+azure\.storage\.blob)\b"),
    ),
    ("azure_blob", "BlobServiceClient", re.compile(r"\bBlobServiceClient\s*\(")),
    ("azure_blob", "ContainerClient", re.compile(r"\bContainerClient\s*\(")),
    ("azure_blob", "BlobClient", re.compile(r"\bBlobClient\s*\(")),
    # Google Cloud Storage
    (
        "gcs",
        "import",
        re.compile(r"^\s*(?:from\s+google\.cloud\.storage|import\s+google\.cloud\.storage)\b"),
    ),
    ("gcs", "Client", re.compile(r"\bstorage\.Client\s*\(")),
    # Built-in open() with file modes
    ("local_file", "open", re.compile(r"\bopen\s*\([^)]*['\"][rwaxb+]+['\"]")),
    # pathlib write/read operations
    ("local_file", "pathlib_write", re.compile(r"\.write_text\s*\(")),
    ("local_file", "pathlib_write", re.compile(r"\.write_bytes\s*\(")),
    ("local_file", "pathlib_read", re.compile(r"\.read_text\s*\(")),
    ("local_file", "pathlib_read", re.compile(r"\.read_bytes\s*\(")),
]


async def scan_file_blob_integrations(file_paths: list[str]) -> list[dict]:
    """Scan Python files for file and blob storage integration patterns.

    Detects usage of boto3 S3, Azure Blob Storage, Google Cloud Storage,
    built-in open(), and pathlib read/write operations.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of dicts with keys: source_file, storage_type,
        operation, line_number, match_text.
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
            for storage_type, operation, pattern in _PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "storage_type": storage_type,
                            "operation": operation,
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

    logger.info("scan_file_blob_integrations_complete", total_matches=len(results))
    return results
