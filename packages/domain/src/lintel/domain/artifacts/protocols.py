"""Protocols for pluggable artifact parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lintel.domain.artifacts.models import CoverageReport, ParsedArtifact


class ArtifactParser(Protocol):
    """Protocol for test result artifact parsers."""

    def parse(self, raw_bytes: bytes) -> ParsedArtifact:
        """Parse raw bytes into a structured ParsedArtifact."""
        ...


class CoverageParser(Protocol):
    """Protocol for coverage report parsers."""

    def parse(self, raw_bytes: bytes) -> CoverageReport:
        """Parse raw bytes into a structured CoverageReport."""
        ...
