"""Unit tests for LCOV parser."""

from __future__ import annotations

from pathlib import Path

from lintel.domain.artifacts.coverage.lcov import LCOVParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_lcov_files() -> None:
    raw = (FIXTURES / "lcov.info").read_bytes()
    parser = LCOVParser()
    report = parser.parse(raw)

    assert len(report.files) == 2
    assert report.files[0].path == "src/math.py"
    assert report.files[1].path == "src/string_utils.py"


def test_parse_lcov_line_coverage() -> None:
    raw = (FIXTURES / "lcov.info").read_bytes()
    parser = LCOVParser()
    report = parser.parse(raw)

    math_file = report.files[0]
    assert math_file.lines_covered == 3
    assert math_file.lines_total == 5
    assert math_file.line_rate == 0.6


def test_parse_lcov_aggregate() -> None:
    raw = (FIXTURES / "lcov.info").read_bytes()
    parser = LCOVParser()
    report = parser.parse(raw)

    assert report.lines_covered == 6
    assert report.lines_total == 8
    assert report.line_rate == 0.75


def test_parse_lcov_branches() -> None:
    raw = (FIXTURES / "lcov.info").read_bytes()
    parser = LCOVParser()
    report = parser.parse(raw)

    assert report.branches_covered == 1
    assert report.branches_total == 2
    assert report.branch_rate == 0.5
