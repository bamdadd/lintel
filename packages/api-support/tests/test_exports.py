"""Tests for the api-support package public API surface."""

from __future__ import annotations


class TestPackageExports:
    """Verify all public symbols are importable from the barrel."""

    def test_store_provider_importable(self) -> None:
        from lintel.api_support import StoreProvider

        assert StoreProvider is not None

    def test_entity_store_importable(self) -> None:
        from lintel.api_support import EntityStore

        assert EntityStore is not None

    def test_dict_store_importable(self) -> None:
        from lintel.api_support import DictStore

        assert DictStore is not None

    def test_project_scoped_dict_store_importable(self) -> None:
        from lintel.api_support import ProjectScopedDictStore

        assert ProjectScopedDictStore is not None

    def test_dispatch_event_importable(self) -> None:
        from lintel.api_support import dispatch_event

        assert callable(dispatch_event)

    def test_dispatch_event_raw_importable(self) -> None:
        from lintel.api_support import dispatch_event_raw

        assert callable(dispatch_event_raw)

    def test_all_matches_exports(self) -> None:
        """__all__ should contain exactly the documented public API."""
        import lintel.api_support as mod

        expected = {
            "DictStore",
            "EntityStore",
            "ProjectScopedDictStore",
            "StoreProvider",
            "dispatch_event",
            "dispatch_event_raw",
        }
        assert set(mod.__all__) == expected
