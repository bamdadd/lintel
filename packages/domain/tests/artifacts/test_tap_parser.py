"""Unit tests for TAP parser."""

from __future__ import annotations

from pathlib import Path

from lintel.domain.artifacts.models import TestCaseStatus
from lintel.domain.artifacts.parsers.tap import TAPParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_tap_basic() -> None:
    raw = (FIXTURES / "sample.tap").read_bytes()
    parser = TAPParser()
    result = parser.parse(raw)

    assert result.total == 5
    assert result.passed == 3
    assert result.failed == 1
    assert result.skipped == 1


def test_parse_tap_statuses() -> None:
    raw = (FIXTURES / "sample.tap").read_bytes()
    parser = TAPParser()
    result = parser.parse(raw)

    cases = result.suites[0].tests
    assert cases[0].status == TestCaseStatus.PASSED
    assert cases[0].name == "addition works"
    assert cases[2].status == TestCaseStatus.FAILED
    assert cases[3].status == TestCaseStatus.SKIPPED


def test_parse_tap_inline() -> None:
    tap = b"1..2\nok 1 - works\nnot ok 2 - broken\n"
    parser = TAPParser()
    result = parser.parse(tap)

    assert result.total == 2
    assert result.passed == 1
    assert result.failed == 1
