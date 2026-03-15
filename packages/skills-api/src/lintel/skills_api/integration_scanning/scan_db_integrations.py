"""Scanner for database client integration patterns."""

from __future__ import annotations

from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    # SQLAlchemy
    ("sqlalchemy", "create_engine", re.compile(r"\bcreate_engine\s*\(")),
    ("sqlalchemy", "sessionmaker", re.compile(r"\bsessionmaker\s*\(")),
    ("sqlalchemy", "declarative_base", re.compile(r"\bdeclarative_base\s*\(")),
    ("sqlalchemy", "import", re.compile(r"^\s*(?:from\s+sqlalchemy|import\s+sqlalchemy)\b")),
    # asyncpg
    ("asyncpg", "connect", re.compile(r"\basyncpg\.connect\s*\(")),
    ("asyncpg", "create_pool", re.compile(r"\basyncpg\.create_pool\s*\(")),
    ("asyncpg", "import", re.compile(r"^\s*(?:from\s+asyncpg|import\s+asyncpg)\b")),
    # pymongo
    ("mongodb", "MongoClient", re.compile(r"\bpymongo\.MongoClient\s*\(")),
    ("mongodb", "MongoClient", re.compile(r"\bMongoClient\s*\(")),
    ("mongodb", "import", re.compile(r"^\s*(?:from\s+pymongo|import\s+pymongo)\b")),
    # redis
    ("redis", "Redis", re.compile(r"\bredis\.Redis\s*\(")),
    ("redis", "StrictRedis", re.compile(r"\bredis\.StrictRedis\s*\(")),
    ("redis", "StrictRedis", re.compile(r"\bStrictRedis\s*\(")),
    # elasticsearch
    ("elasticsearch", "Elasticsearch", re.compile(r"\bElasticsearch\s*\(")),
    (
        "elasticsearch",
        "import",
        re.compile(r"^\s*(?:from\s+elasticsearch|import\s+elasticsearch)\b"),
    ),
]


async def scan_db_integrations(file_paths: list[str]) -> list[dict]:
    """Scan Python files for database client integration patterns.

    Detects usage of SQLAlchemy, asyncpg, pymongo, redis, and elasticsearch.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of dicts with keys: source_file, db_type,
        client_pattern, line_number, match_text.
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
            for db_type, client_pattern, pattern in _PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "db_type": db_type,
                            "client_pattern": client_pattern,
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

    logger.info("scan_db_integrations_complete", total_matches=len(results))
    return results
