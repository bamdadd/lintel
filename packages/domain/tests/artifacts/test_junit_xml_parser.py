"""Unit tests for JUnit XML parser."""

from __future__ import annotations

from pathlib import Path

from lintel.domain.artifacts.models import TestCaseStatus
from lintel.domain.artifacts.parsers.junit_xml import JUnitXMLParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_junit_xml_suites() -> None:
    raw = (FIXTURES / "sample.junit.xml").read_bytes()
    parser = JUnitXMLParser()
    result = parser.parse(raw)

    assert len(result.suites) == 2
    assert result.total == 6
    assert result.passed == 3
    assert result.failed == 1
    assert result.errors == 1
    assert result.skipped == 1


def test_parse_junit_xml_case_details() -> None:
    raw = (FIXTURES / "sample.junit.xml").read_bytes()
    parser = JUnitXMLParser()
    result = parser.parse(raw)

    math_suite = result.suites[0]
    assert math_suite.name == "com.example.MathTest"
    assert len(math_suite.tests) == 4

    # Check failed test
    division_case = math_suite.tests[2]
    assert division_case.name == "test_division"
    assert division_case.status == TestCaseStatus.FAILED
    assert "AssertionError" in division_case.message

    # Check skipped test
    multiply_case = math_suite.tests[3]
    assert multiply_case.status == TestCaseStatus.SKIPPED


def test_parse_junit_xml_error_case() -> None:
    raw = (FIXTURES / "sample.junit.xml").read_bytes()
    parser = JUnitXMLParser()
    result = parser.parse(raw)

    string_suite = result.suites[1]
    error_case = string_suite.tests[1]
    assert error_case.status == TestCaseStatus.ERROR
    assert "NullPointerException" in error_case.message


def test_parse_junit_xml_durations() -> None:
    raw = (FIXTURES / "sample.junit.xml").read_bytes()
    parser = JUnitXMLParser()
    result = parser.parse(raw)

    assert result.duration_ms > 0
    math_suite = result.suites[0]
    assert math_suite.tests[0].duration_ms == 10


def test_parse_single_testsuite() -> None:
    xml = b"""<?xml version="1.0"?>
    <testsuite name="single" tests="1">
      <testcase name="test_one" classname="TestSingle" time="0.001"/>
    </testsuite>"""
    parser = JUnitXMLParser()
    result = parser.parse(xml)

    assert len(result.suites) == 1
    assert result.total == 1
    assert result.passed == 1


def test_pass_rate() -> None:
    raw = (FIXTURES / "sample.junit.xml").read_bytes()
    parser = JUnitXMLParser()
    result = parser.parse(raw)

    # 3 passed out of 6 total = 50%
    assert result.pass_rate == 50.0
