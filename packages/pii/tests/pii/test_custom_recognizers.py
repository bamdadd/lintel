"""Tests for custom PII recognizers (API keys, connection strings)."""

from __future__ import annotations

from lintel.pii.custom_recognizers import (
    API_KEY_PATTERNS,
    CONNECTION_STRING_PATTERNS,
    create_api_key_recognizer,
    create_connection_string_recognizer,
)


class TestApiKeyPatterns:
    def test_pattern_list_not_empty(self) -> None:
        assert len(API_KEY_PATTERNS) >= 3

    def test_generic_api_key_matches(self) -> None:
        import re

        pattern = API_KEY_PATTERNS[0]
        text = "api_key = 'sk_test_abcdef1234567890ABCD'"
        assert re.search(pattern.regex, text)

    def test_bearer_token_matches(self) -> None:
        import re

        pattern = API_KEY_PATTERNS[1]
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        assert re.search(pattern.regex, text)

    def test_aws_access_key_matches(self) -> None:
        import re

        pattern = API_KEY_PATTERNS[2]
        text = "aws_key = AKIAIOSFODNN7EXAMPLE"
        assert re.search(pattern.regex, text)

    def test_aws_key_no_false_positive(self) -> None:
        import re

        pattern = API_KEY_PATTERNS[2]
        text = "this is just normal text"
        assert re.search(pattern.regex, text) is None


class TestConnectionStringPatterns:
    def test_pattern_list_not_empty(self) -> None:
        assert len(CONNECTION_STRING_PATTERNS) >= 2

    def test_postgres_url_matches(self) -> None:
        import re

        pattern = CONNECTION_STRING_PATTERNS[0]
        text = "DATABASE_URL=postgresql://user:pass@localhost:5432/db"
        assert re.search(pattern.regex, text)

    def test_redis_url_matches(self) -> None:
        import re

        pattern = CONNECTION_STRING_PATTERNS[1]
        text = "REDIS_URL=redis://localhost:6379/0"
        assert re.search(pattern.regex, text)

    def test_mongodb_url_matches(self) -> None:
        import re

        pattern = CONNECTION_STRING_PATTERNS[1]
        text = "MONGO=mongodb://admin:secret@mongo:27017/mydb"
        assert re.search(pattern.regex, text)


class TestRecognizerFactory:
    def test_create_api_key_recognizer(self) -> None:
        recognizer = create_api_key_recognizer()
        assert recognizer.supported_entities == ["API_KEY"]
        assert len(recognizer.patterns) == len(API_KEY_PATTERNS)

    def test_create_connection_string_recognizer(self) -> None:
        recognizer = create_connection_string_recognizer()
        assert recognizer.supported_entities == ["CONNECTION_STRING"]
        assert len(recognizer.patterns) == len(CONNECTION_STRING_PATTERNS)
