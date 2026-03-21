"""Lintel projection read-models."""

from lintel.projections.base import ProjectionBase
from lintel.projections.memory_consolidation import MemoryConsolidationProjection

__all__ = [
    "MemoryConsolidationProjection",
    "ProjectionBase",
]
