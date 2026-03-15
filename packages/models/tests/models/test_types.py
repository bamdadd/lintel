"""Tests for model domain types."""

from __future__ import annotations

import dataclasses

import pytest

from lintel.models.types import ModelPolicy


class TestModelPolicy:
    def test_frozen(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        with pytest.raises(dataclasses.FrozenInstanceError):
            policy.provider = "openai"  # type: ignore[misc]

    def test_defaults(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        assert policy.max_tokens == 4096
        assert policy.temperature == 0.0

    def test_custom_values(self) -> None:
        policy = ModelPolicy(
            provider="openai",
            model_name="gpt-4",
            max_tokens=8192,
            temperature=0.7,
        )
        assert policy.provider == "openai"
        assert policy.model_name == "gpt-4"
        assert policy.max_tokens == 8192
        assert policy.temperature == 0.7

    def test_equality(self) -> None:
        p1 = ModelPolicy(provider="a", model_name="b")
        p2 = ModelPolicy(provider="a", model_name="b")
        p3 = ModelPolicy(provider="a", model_name="c")
        assert p1 == p2
        assert p1 != p3
