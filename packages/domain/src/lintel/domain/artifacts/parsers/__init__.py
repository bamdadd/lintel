"""Pluggable artifact parsers for test result formats."""

from lintel.domain.artifacts.parsers.junit_xml import JUnitXMLParser
from lintel.domain.artifacts.parsers.pytest_json import PytestJSONParser
from lintel.domain.artifacts.parsers.registry import ParserRegistry
from lintel.domain.artifacts.parsers.tap import TAPParser

__all__ = [
    "JUnitXMLParser",
    "ParserRegistry",
    "PytestJSONParser",
    "TAPParser",
]
