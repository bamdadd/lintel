"""Domain model extraction types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EntityType(StrEnum):
    """Kind of extracted entity."""

    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    DATACLASS = "dataclass"
    PROTOCOL = "protocol"


class RelationshipKind(StrEnum):
    """Kind of relationship between entities."""

    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    CONTAINS = "contains"
    USES = "uses"


@dataclass(frozen=True)
class FieldInfo:
    """A field on an extracted entity."""

    name: str
    type_annotation: str
    default: str | None = None


@dataclass(frozen=True)
class MethodInfo:
    """A method on an extracted entity."""

    name: str
    parameters: tuple[str, ...] = ()
    return_type: str = "None"
    is_async: bool = False


@dataclass(frozen=True)
class ExtractedEntity:
    """An entity extracted from source code."""

    name: str
    entity_type: EntityType
    module_path: str
    fields: tuple[FieldInfo, ...] = ()
    methods: tuple[MethodInfo, ...] = ()
    docstring: str = ""
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relationship:
    """A directed relationship between two entities."""

    source: str
    target: str
    kind: RelationshipKind


@dataclass(frozen=True)
class BoundedContext:
    """A bounded context grouping related entities."""

    name: str
    entity_names: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class DomainModel:
    """Complete domain model extracted from a codebase."""

    entities: tuple[ExtractedEntity, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    bounded_contexts: tuple[BoundedContext, ...] = field(default=())
