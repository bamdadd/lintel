"""Unit tests for coverage.py JSON parser."""

from __future__ import annotations

from pathlib import Path

from lintel.domain.artifacts.coverage.coverage_py import CoveragePyParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_coverage_py_files() -> None:
    raw = (FIXTURES / "coverage.json").read_bytes()
    parser = CoveragePyParser()
    report = parser.parse(raw)

    assert len(report.files) == 2


def test_parse_coverage_py_line_coverage() -> None:
    raw = (FIXTURES / "coverage.json").read_bytes()
    parser = CoveragePyParser()
    report = parser.parse(raw)

    # Find math.py file
    math_file = next(f for f in report.files if f.path == "src/math.py")
    assert math_file.lines_covered == 3
    assert math_file.lines_total == 5


def test_parse_coverage_py_aggregate() -> None:
    raw = (FIXTURES / "coverage.json").read_bytes()
    parser = CoveragePyParser()
    report = parser.parse(raw)

    assert report.lines_covered == 6
    assert report.lines_total == 8
    assert report.line_rate == 0.75


def test_parse_coverage_py_branches() -> None:
    raw = (FIXTURES / "coverage.json").read_bytes()
    parser = CoveragePyParser()
    report = parser.parse(raw)

    assert report.branches_covered == 1
    assert report.branches_total == 2
    assert report.branch_rate == 0.5
