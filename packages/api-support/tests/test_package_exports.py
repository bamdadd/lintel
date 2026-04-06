"""Tests that the api-support package exports its public API from __init__."""

from __future__ import annotations


def test_package_exports_store_provider() -> None:
    """StoreProvider is importable from lintel.api_support."""
    from lintel.api_support import StoreProvider

    provider: StoreProvider[int] = StoreProvider()
    provider.override(42)
    assert provider.get() == 42


def test_package_exports_entity_store() -> None:
    """EntityStore protocol is importable from lintel.api_support."""
    from lintel.api_support import EntityStore

    assert hasattr(EntityStore, "__protocol_attrs__")


def test_package_exports_dict_store() -> None:
    """DictStore protocol is importable from lintel.api_support."""
    from lintel.api_support import DictStore

    assert hasattr(DictStore, "__protocol_attrs__")


def test_package_exports_project_scoped_dict_store() -> None:
    """ProjectScopedDictStore protocol is importable from lintel.api_support."""
    from lintel.api_support import ProjectScopedDictStore

    assert hasattr(ProjectScopedDictStore, "__protocol_attrs__")


def test_package_exports_dispatch_event() -> None:
    """dispatch_event is importable from lintel.api_support."""
    from lintel.api_support import dispatch_event

    assert callable(dispatch_event)


def test_package_exports_dispatch_event_raw() -> None:
    """dispatch_event_raw is importable from lintel.api_support."""
    from lintel.api_support import dispatch_event_raw

    assert callable(dispatch_event_raw)
