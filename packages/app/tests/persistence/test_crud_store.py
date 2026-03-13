"""Tests for PostgresCrudStore._to_instance deserialization."""

from __future__ import annotations

import dataclasses
import enum
from unittest.mock import AsyncMock

from lintel.infrastructure.persistence.crud_store import PostgresCrudStore


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class Status(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclasses.dataclass(frozen=True)
class SampleEntity:
    entity_id: str
    color: Color
    status: Status
    tags: tuple[str, ...] = ()
    labels: frozenset[str] = frozenset()
    name: str = ""


class TestToInstance:
    def _make_store(self) -> PostgresCrudStore:
        pool = AsyncMock()
        return PostgresCrudStore(pool, "sample", "entity_id", SampleEntity)

    def test_strenum_deserialized_from_string(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": "red",
                "status": "active",
            }
        )
        assert isinstance(result.color, Color)
        assert result.color is Color.RED
        assert result.color.value == "red"

    def test_enum_deserialized_from_string(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": "blue",
                "status": "inactive",
            }
        )
        assert isinstance(result.status, Status)
        assert result.status is Status.INACTIVE

    def test_tuple_deserialized_from_list(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": "red",
                "status": "active",
                "tags": ["a", "b"],
            }
        )
        assert isinstance(result.tags, tuple)
        assert result.tags == ("a", "b")

    def test_frozenset_deserialized_from_list(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": "red",
                "status": "active",
                "labels": ["x", "y"],
            }
        )
        assert isinstance(result.labels, frozenset)
        assert result.labels == frozenset({"x", "y"})

    def test_extra_keys_filtered_out(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": "red",
                "status": "active",
                "unknown_field": "ignored",
            }
        )
        assert result.entity_id == "e1"
        assert not hasattr(result, "unknown_field")

    def test_enum_value_already_correct_type(self) -> None:
        store = self._make_store()
        result = store._to_instance(
            {
                "entity_id": "e1",
                "color": Color.BLUE,
                "status": Status.ACTIVE,
            }
        )
        assert result.color is Color.BLUE
        assert result.status is Status.ACTIVE

    def test_ai_provider_type_round_trip(self) -> None:
        """Regression test: provider_type must be AIProviderType, not str."""
        from lintel.contracts.types import AIProvider, AIProviderType

        pool = AsyncMock()
        store = PostgresCrudStore(pool, "ai_provider", "provider_id", AIProvider)
        result = store._to_instance(
            {
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "Local Ollama",
                "api_base": "http://localhost:11434",
                "is_default": False,
                "models": [],
            }
        )
        assert isinstance(result.provider_type, AIProviderType)
        assert result.provider_type is AIProviderType.OLLAMA
        assert result.provider_type.value == "ollama"
