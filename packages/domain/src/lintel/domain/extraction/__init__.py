"""Domain model extraction — analyse source code to extract entities and relationships."""

from lintel.domain.extraction.extractor import DomainModelExtractor
from lintel.domain.extraction.types import (
    BoundedContext,
    DomainModel,
    EntityType,
    ExtractedEntity,
    FieldInfo,
    MethodInfo,
    Relationship,
    RelationshipKind,
)

__all__ = [
    "BoundedContext",
    "DomainModel",
    "DomainModelExtractor",
    "EntityType",
    "ExtractedEntity",
    "FieldInfo",
    "MethodInfo",
    "Relationship",
    "RelationshipKind",
]
