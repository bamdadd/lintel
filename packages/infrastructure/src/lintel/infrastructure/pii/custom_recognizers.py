"""Custom Presidio recognizers for code-specific patterns."""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

API_KEY_PATTERNS = [
    Pattern("api_key_generic", r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})", 0.7),
    Pattern("bearer_token", r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", 0.8),
    Pattern("aws_access_key", r"AKIA[0-9A-Z]{16}", 0.9),
]

CONNECTION_STRING_PATTERNS = [
    Pattern(
        "postgres_url",
        r"postgres(?:ql)?://[^\s'\"]+",
        0.8,
    ),
    Pattern(
        "generic_connection",
        r"(?:mysql|redis|mongodb|amqp)://[^\s'\"]+",
        0.8,
    ),
]


def create_api_key_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="API_KEY",
        patterns=API_KEY_PATTERNS,
    )


def create_connection_string_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="CONNECTION_STRING",
        patterns=CONNECTION_STRING_PATTERNS,
    )
