"""Tests for tech stack domain types."""

from __future__ import annotations

import pytest

from lintel.domain.techstack.types import TechStackCategory, TechStackEntry, TechStackReport


class TestTechStackEntry:
    def test_frozen(self) -> None:
        entry = TechStackEntry(
            name="Python",
            version="3.12",
            category=TechStackCategory.LANGUAGE,
            source_file="pyproject.toml",
            confidence=1.0,
        )
        with pytest.raises(AttributeError):
            entry.name = "Rust"  # type: ignore[misc]

    def test_confidence_validation_too_high(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            TechStackEntry(
                name="x",
                version="1",
                category=TechStackCategory.LIBRARY,
                source_file="f",
                confidence=1.5,
            )

    def test_confidence_validation_negative(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            TechStackEntry(
                name="x",
                version="1",
                category=TechStackCategory.LIBRARY,
                source_file="f",
                confidence=-0.1,
            )

    def test_confidence_boundary_values(self) -> None:
        e0 = TechStackEntry("a", "1", TechStackCategory.TOOL, "f", 0.0)
        e1 = TechStackEntry("a", "1", TechStackCategory.TOOL, "f", 1.0)
        assert e0.confidence == 0.0
        assert e1.confidence == 1.0


class TestTechStackCategory:
    def test_all_values(self) -> None:
        assert len(TechStackCategory) == 7
        assert TechStackCategory.LANGUAGE == "language"
        assert TechStackCategory.INFRASTRUCTURE == "infrastructure"


class TestTechStackReport:
    def test_from_entries_deduplicates(self) -> None:
        entries = [
            TechStackEntry("fastapi", "0.100", TechStackCategory.FRAMEWORK, "a.toml", 0.7),
            TechStackEntry("FastAPI", "0.110", TechStackCategory.FRAMEWORK, "b.toml", 0.9),
        ]
        report = TechStackReport.from_entries(entries)
        assert len(report.entries) == 1
        assert report.entries[0].version == "0.110"  # higher confidence wins

    def test_from_entries_tracks_source_files(self) -> None:
        entries = [
            TechStackEntry("x", "1", TechStackCategory.LIBRARY, "a.txt", 0.5),
            TechStackEntry("y", "2", TechStackCategory.LIBRARY, "b.txt", 0.5),
        ]
        report = TechStackReport.from_entries(entries)
        assert set(report.source_files) == {"a.txt", "b.txt"}

    def test_from_entries_empty(self) -> None:
        report = TechStackReport.from_entries([])
        assert report.entries == ()
        assert report.source_files == ()

    def test_entries_sorted_by_category_then_name(self) -> None:
        entries = [
            TechStackEntry("zlib", "1", TechStackCategory.LIBRARY, "f", 0.5),
            TechStackEntry("Python", "3", TechStackCategory.LANGUAGE, "f", 0.5),
            TechStackEntry("alib", "1", TechStackCategory.LIBRARY, "f", 0.5),
        ]
        report = TechStackReport.from_entries(entries)
        names = [e.name for e in report.entries]
        assert names == ["Python", "alib", "zlib"]
