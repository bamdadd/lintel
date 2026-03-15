"""Tests for StoreProvider."""

import pytest

from lintel.api_support.provider import StoreProvider


class TestStoreProvider:
    def test_raises_when_not_configured(self) -> None:
        provider = StoreProvider()
        with pytest.raises(RuntimeError, match="Store not configured"):
            provider()

    def test_returns_instance_after_override(self) -> None:
        provider = StoreProvider()
        sentinel = object()
        provider.override(sentinel)
        assert provider() is sentinel

    def test_override_replaces_previous(self) -> None:
        provider = StoreProvider()
        first = object()
        second = object()
        provider.override(first)
        provider.override(second)
        assert provider() is second

    def test_override_with_none_resets(self) -> None:
        provider = StoreProvider()
        provider.override(object())
        provider.override(None)
        with pytest.raises(RuntimeError):
            provider()
