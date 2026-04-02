"""Scanner for asynchronous / message-broker integration patterns."""

from __future__ import annotations

from pathlib import Path
import re

import structlog

logger = structlog.get_logger(__name__)

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    # kafka-python
    ("kafka", "kafka", re.compile(r"\b(KafkaProducer|KafkaConsumer)\s*\(")),
    # aiokafka
    ("aiokafka", "kafka", re.compile(r"\b(AIOKafkaProducer|AIOKafkaConsumer)\s*\(")),
    ("aiokafka", "kafka", re.compile(r"^\s*(?:from\s+aiokafka|import\s+aiokafka)\b")),
    # NATS
    ("nats", "nats", re.compile(r"\bnats\.connect\s*\(")),
    ("nats", "nats", re.compile(r"\bNATS\s*\(\s*\)")),
    ("nats", "nats", re.compile(r"^\s*(?:from\s+nats|import\s+nats)\b")),
    # RabbitMQ via pika
    (
        "rabbitmq",
        "amqp",
        re.compile(r"\bpika\.(BlockingConnection|SelectConnection|ConnectionParameters)\s*\("),
    ),
    ("rabbitmq", "amqp", re.compile(r"^\s*(?:from\s+pika|import\s+pika)\b")),
    # Redis pub/sub via aioredis
    (
        "redis_pubsub",
        "redis",
        re.compile(r"\baioredis\.(from_url|create_redis|create_redis_pool)\s*\("),
    ),
    ("redis_pubsub", "redis", re.compile(r"^\s*(?:from\s+aioredis|import\s+aioredis)\b")),
    # Redis pub/sub via redis-py
    ("redis_pubsub", "redis", re.compile(r"\bredis\.Redis\s*\(.*\)\.pubsub\s*\(")),
    ("redis_pubsub", "redis", re.compile(r"\.pubsub\s*\(")),
]


async def scan_async_integrations(file_paths: list[str]) -> list[dict]:
    """Scan Python files for async / message-broker integration patterns.

    Detects usage of Kafka, NATS, RabbitMQ (pika), and Redis pub/sub.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of dicts with keys: source_file, pattern_type,
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
            for pattern_type, protocol, pattern in _PATTERNS:
                match = pattern.search(line)
                if match:
                    results.append(
                        {
                            "source_file": file_path_str,
                            "pattern_type": pattern_type,
                            "protocol": protocol,
                            "line_number": line_number,
                            "match_text": match.group(0).strip(),
                        }
                    )

    logger.info("scan_async_integrations_complete", total_matches=len(results))
    return results
