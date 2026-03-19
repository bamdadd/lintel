"""Registry for mapping file types to artifact parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.domain.artifacts.parsers.junit_xml import JUnitXMLParser
from lintel.domain.artifacts.parsers.pytest_json import PytestJSONParser
from lintel.domain.artifacts.parsers.tap import TAPParser

if TYPE_CHECKING:
    from lintel.domain.artifacts.models import CoverageReport, ParsedArtifact
    from lintel.domain.artifacts.protocols import ArtifactParser, CoverageParser


class ParserRegistry:
    """Registry mapping MIME types and file extensions to parsers."""

    def __init__(self) -> None:
        self._artifact_parsers: dict[str, ArtifactParser] = {}
        self._coverage_parsers: dict[str, CoverageParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        junit = JUnitXMLParser()
        pytest_json = PytestJSONParser()
        tap = TAPParser()

        # By extension
        self._artifact_parsers[".xml"] = junit
        self._artifact_parsers[".junit.xml"] = junit
        self._artifact_parsers[".json"] = pytest_json
        self._artifact_parsers[".tap"] = tap

        # By MIME type
        self._artifact_parsers["application/xml"] = junit
        self._artifact_parsers["text/xml"] = junit
        self._artifact_parsers["application/json"] = pytest_json
        self._artifact_parsers["text/plain"] = tap

        # Coverage parsers
        from lintel.domain.artifacts.coverage.coverage_py import CoveragePyParser
        from lintel.domain.artifacts.coverage.lcov import LCOVParser

        lcov = LCOVParser()
        coveragepy = CoveragePyParser()

        self._coverage_parsers[".info"] = lcov
        self._coverage_parsers[".lcov"] = lcov
        self._coverage_parsers[".json"] = coveragepy
        self._coverage_parsers["text/plain"] = lcov

    def register_artifact_parser(
        self,
        key: str,
        parser: ArtifactParser,
    ) -> None:
        """Register a parser by extension or MIME type."""
        self._artifact_parsers[key] = parser

    def register_coverage_parser(
        self,
        key: str,
        parser: CoverageParser,
    ) -> None:
        """Register a coverage parser by extension or MIME type."""
        self._coverage_parsers[key] = parser

    def get_artifact_parser(
        self,
        *,
        mime_type: str | None = None,
        extension: str | None = None,
    ) -> ArtifactParser:
        """Look up an artifact parser by MIME type or extension."""
        if extension and extension in self._artifact_parsers:
            return self._artifact_parsers[extension]
        if mime_type and mime_type in self._artifact_parsers:
            return self._artifact_parsers[mime_type]
        msg = f"No artifact parser for mime_type={mime_type}, extension={extension}"
        raise ValueError(msg)

    def get_coverage_parser(
        self,
        *,
        mime_type: str | None = None,
        extension: str | None = None,
    ) -> CoverageParser:
        """Look up a coverage parser by MIME type or extension."""
        if extension and extension in self._coverage_parsers:
            return self._coverage_parsers[extension]
        if mime_type and mime_type in self._coverage_parsers:
            return self._coverage_parsers[mime_type]
        msg = f"No coverage parser for mime_type={mime_type}, extension={extension}"
        raise ValueError(msg)

    def parse_artifact(
        self,
        raw_bytes: bytes,
        *,
        mime_type: str | None = None,
        extension: str | None = None,
    ) -> ParsedArtifact:
        """Convenience method to find parser and parse in one call."""
        parser = self.get_artifact_parser(mime_type=mime_type, extension=extension)
        return parser.parse(raw_bytes)

    def parse_coverage(
        self,
        raw_bytes: bytes,
        *,
        mime_type: str | None = None,
        extension: str | None = None,
    ) -> CoverageReport:
        """Convenience method to find coverage parser and parse in one call."""
        parser = self.get_coverage_parser(mime_type=mime_type, extension=extension)
        return parser.parse(raw_bytes)
