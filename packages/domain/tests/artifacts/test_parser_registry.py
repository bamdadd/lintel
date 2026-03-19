"""Unit tests for parser registry."""

from __future__ import annotations

import pytest

from lintel.domain.artifacts.parsers.registry import ParserRegistry


def test_get_artifact_parser_by_extension() -> None:
    registry = ParserRegistry()
    parser = registry.get_artifact_parser(extension=".xml")
    assert parser is not None


def test_get_artifact_parser_by_mime_type() -> None:
    registry = ParserRegistry()
    parser = registry.get_artifact_parser(mime_type="application/xml")
    assert parser is not None


def test_get_coverage_parser_by_extension() -> None:
    registry = ParserRegistry()
    parser = registry.get_coverage_parser(extension=".info")
    assert parser is not None


def test_get_artifact_parser_unknown_raises() -> None:
    registry = ParserRegistry()
    with pytest.raises(ValueError, match="No artifact parser"):
        registry.get_artifact_parser(extension=".xyz")


def test_get_coverage_parser_unknown_raises() -> None:
    registry = ParserRegistry()
    with pytest.raises(ValueError, match="No coverage parser"):
        registry.get_coverage_parser(extension=".xyz")


def test_parse_artifact_convenience() -> None:
    registry = ParserRegistry()
    xml = b"""<?xml version="1.0"?>
    <testsuite name="test" tests="1">
      <testcase name="test_one" classname="Test" time="0.001"/>
    </testsuite>"""
    result = registry.parse_artifact(xml, extension=".xml")
    assert result.total == 1
    assert result.passed == 1


def test_register_custom_parser() -> None:
    from lintel.domain.artifacts.parsers.junit_xml import JUnitXMLParser

    registry = ParserRegistry()
    registry.register_artifact_parser(".custom", JUnitXMLParser())
    parser = registry.get_artifact_parser(extension=".custom")
    assert parser is not None
