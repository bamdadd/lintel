"""Store protocols for CRUD entity packages.

These protocols define the interface that both in-memory and Postgres store
implementations must satisfy. Route handlers type-hint against these protocols
so they work with any backend.

Two shapes:

- ``EntityStore[T]`` — stores that accept/return typed dataclass entities
- ``DictStore`` — stores that accept/return plain dicts (validated externally)
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class EntityStore(Protocol[T]):
    """Protocol for stores that operate on typed entities.

    Used by: users, teams, policies, triggers, environments, variables, etc.
    """

    async def add(self, entity: T) -> None: ...
    async def get(self, entity_id: str) -> T | None: ...
    async def list_all(self) -> list[T]: ...
    async def update(self, entity: T) -> None: ...
    async def remove(self, entity_id: str) -> None: ...


@runtime_checkable
class DictStore(Protocol):
    """Protocol for stores that operate on plain dicts.

    Used by: boards, tags, compliance entities, etc.
    """

    async def add(self, data: dict[str, Any]) -> None: ...
    async def get(self, entity_id: str) -> dict[str, Any] | None: ...
    async def remove(self, entity_id: str) -> None: ...


@runtime_checkable
class ProjectScopedDictStore(DictStore, Protocol):
    """DictStore with project-scoped listing."""

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]: ...
