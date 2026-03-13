"""Tests for lintel.config — typed configuration via pydantic-settings."""

from __future__ import annotations

from unittest.mock import patch

from lintel.config import (
    DatabaseSettings,
    ModelSettings,
    NATSSettings,
    PIISettings,
    SandboxSettings,
    Settings,
    SlackSettings,
)


class TestDatabaseSettings:
    def test_defaults(self) -> None:
        s = DatabaseSettings()
        assert s.dsn == "postgresql://lintel:lintel@localhost:5432/lintel"
        assert s.pool_min == 5
        assert s.pool_max == 20

    def test_env_override(self) -> None:
        with patch.dict(
            "os.environ",
            {"LINTEL_DB_DSN": "postgresql://x:x@db:5432/x", "LINTEL_DB_POOL_MIN": "2"},
        ):
            s = DatabaseSettings()
            assert s.dsn == "postgresql://x:x@db:5432/x"
            assert s.pool_min == 2


class TestNATSSettings:
    def test_defaults(self) -> None:
        s = NATSSettings()
        assert s.url == "nats://localhost:4222"
        assert s.enabled is False


class TestSlackSettings:
    def test_defaults(self) -> None:
        s = SlackSettings()
        assert s.bot_token == ""
        assert s.signing_secret == ""
        assert s.app_token == ""

    def test_env_override(self) -> None:
        with patch.dict("os.environ", {"LINTEL_SLACK_BOT_TOKEN": "xoxb-test"}):
            s = SlackSettings()
            assert s.bot_token == "xoxb-test"


class TestPIISettings:
    def test_defaults(self) -> None:
        s = PIISettings()
        assert s.risk_threshold == 0.6
        assert s.vault_encryption_key == ""


class TestModelSettings:
    def test_defaults(self) -> None:
        s = ModelSettings()
        assert s.default_provider == "anthropic"
        assert s.default_model == "claude-sonnet-4-20250514"
        assert s.fallback_provider == "ollama"
        assert s.fallback_model == "llama3.1:8b"


class TestSandboxSettings:
    def test_defaults(self) -> None:
        s = SandboxSettings()
        assert s.docker_host == "unix:///var/run/docker.sock"
        assert s.max_cpu == "2"
        assert s.max_memory == "4g"
        assert s.timeout_seconds == 1800
        assert s.network_mode == "none"


class TestSettings:
    def test_root_defaults(self) -> None:
        s = Settings()
        assert s.log_level == "INFO"
        assert s.log_format == "json"
        assert s.otel_endpoint == ""
        assert s.environment == "development"

    def test_nested_subsystems(self) -> None:
        s = Settings()
        assert isinstance(s.db, DatabaseSettings)
        assert isinstance(s.nats, NATSSettings)
        assert isinstance(s.slack, SlackSettings)
        assert isinstance(s.pii, PIISettings)
        assert isinstance(s.model, ModelSettings)
        assert isinstance(s.sandbox, SandboxSettings)
