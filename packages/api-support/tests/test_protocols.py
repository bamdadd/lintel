"""Tests for store protocols."""

from __future__ import annotations

from typing import Any

from lintel.api_support.protocols import DictStore, EntityStore, ProjectScopedDictStore


class FakeEntity:
    entity_id: str = "e-1"


class FakeEntityStore:
    async def add(self, entity: FakeEntity) -> None: ...
    async def get(self, entity_id: str) -> FakeEntity | None: ...
    async def list_all(self) -> list[FakeEntity]: ...
    async def update(self, entity: FakeEntity) -> None: ...
    async def remove(self, entity_id: str) -> None: ...


class FakeDictStore:
    async def add(self, data: dict[str, Any]) -> None: ...
    async def get(self, entity_id: str) -> dict[str, Any] | None: ...
    async def remove(self, entity_id: str) -> None: ...


class FakeProjectScopedStore(FakeDictStore):
    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]: ...


class TestEntityStoreProtocol:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(FakeEntityStore(), EntityStore)

    def test_missing_method_fails(self) -> None:
        class Incomplete:
            async def add(self, entity: FakeEntity) -> None: ...

        assert not isinstance(Incomplete(), EntityStore)


class TestDictStoreProtocol:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(FakeDictStore(), DictStore)


class TestProjectScopedDictStoreProtocol:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(FakeProjectScopedStore(), ProjectScopedDictStore)

    def test_dict_store_without_list_by_project_fails(self) -> None:
        assert not isinstance(FakeDictStore(), ProjectScopedDictStore)
