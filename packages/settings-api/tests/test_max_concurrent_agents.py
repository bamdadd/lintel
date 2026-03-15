"""Tests for LINTEL_MAX_CONCURRENT_AGENTS setting."""

from __future__ import annotations


class TestMaxConcurrentAgentsSetting:
    def test_default_value(self) -> None:
        from lintel.config import Settings

        settings = Settings()
        assert settings.max_concurrent_agents == 5

    def test_configurable_via_env(self, monkeypatch: object) -> None:
        monkeypatch.setenv("LINTEL_MAX_CONCURRENT_AGENTS", "10")  # type: ignore[attr-defined]
        # Re-instantiate to pick up env var
        from lintel.config import Settings

        settings = Settings()
        assert settings.max_concurrent_agents == 10

    def test_exported_from_config(self) -> None:
        from lintel.config import Settings

        s = Settings()
        assert hasattr(s, "max_concurrent_agents")
        assert isinstance(s.max_concurrent_agents, int)
