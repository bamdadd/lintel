"""Unit tests for pytest JSON parser."""

from __future__ import annotations

from pathlib import Path

from lintel.domain.artifacts.models import TestCaseStatus
from lintel.domain.artifacts.parsers.pytest_json import PytestJSONParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_pytest_json_basic() -> None:
    raw = (FIXTURES / "pytest_report.json").read_bytes()
    parser = PytestJSONParser()
    result = parser.parse(raw)

    assert result.total == 5
    assert result.passed == 3
    assert result.failed == 1
    assert result.skipped == 1


def test_parse_pytest_json_suites_by_module() -> None:
    raw = (FIXTURES / "pytest_report.json").read_bytes()
    parser = PytestJSONParser()
    result = parser.parse(raw)

    suite_names = {s.name for s in result.suites}
    assert "tests/test_math.py" in suite_names
    assert "tests/test_strings.py" in suite_names


def test_parse_pytest_json_failure_message() -> None:
    raw = (FIXTURES / "pytest_report.json").read_bytes()
    parser = PytestJSONParser()
    result = parser.parse(raw)

    # Find the failed test
    failed_cases = [c for s in result.suites for c in s.tests if c.status == TestCaseStatus.FAILED]
    assert len(failed_cases) == 1
    assert "AssertionError" in failed_cases[0].message
