"""Coverage report parsers."""

from lintel.domain.artifacts.coverage.coverage_py import CoveragePyParser
from lintel.domain.artifacts.coverage.lcov import LCOVParser

__all__ = [
    "CoveragePyParser",
    "LCOVParser",
]
