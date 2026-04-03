"""Tests for ContextInjector service."""

from __future__ import annotations

from typing import Any

import pytest

from lintel.context_injection.injector import (
    ContextInjector,
    _build_search_queries,
    _deduplicate_snippets,
    _extract_keywords,
    _rank_snippets,
    _trim_to_budget,
    estimate_tokens,
)
from lintel.context_injection.types import ContextBudget, ContextSnippet, InjectedContext

# ---------------------------------------------------------------------------
# Fake searcher
# ---------------------------------------------------------------------------


class FakeCodebaseIndexSearcher:
    """In-memory searcher for testing."""

    def __init__(self) -> None:
        self.indices: list[dict[str, Any]] = []
        self.entries: list[dict[str, Any]] = []

    async def list_indices_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [i for i in self.indices if i.get("project_id") == project_id]

    async def search(self, index_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        q_lower = query.lower()
        for entry in self.entries:
            if entry.get("index_id") != index_id:
                continue
            content = entry.get("content", "").lower()
            if q_lower in content:
                results.append(
                    {
                        "file_path": entry.get("file_path", ""),
                        "content": entry.get("content", ""),
                        "score": 1.0,
                        "language": entry.get("language", ""),
                        "start_line": entry.get("start_line", 0),
                        "end_line": entry.get("end_line", 0),
                    }
                )
            if len(results) >= limit:
                break
        return results


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_basic(self) -> None:
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("a" * 100) == 25

    def test_empty_returns_one(self) -> None:
        assert estimate_tokens("") == 1


class TestExtractKeywords:
    def test_filters_stop_words(self) -> None:
        kws = _extract_keywords("add a new feature to the system")
        assert "add" in kws
        assert "feature" in kws
        assert "system" in kws
        assert "the" not in kws
        assert "a" not in kws

    def test_filters_short_words(self) -> None:
        kws = _extract_keywords("do it in go")
        assert "do" not in kws
        assert "it" not in kws
        assert "in" not in kws
        assert "go" not in kws

    def test_extracts_identifiers(self) -> None:
        kws = _extract_keywords("implement ContextInjector service")
        assert "implement" in kws
        assert "contextinjector" in kws
        assert "service" in kws


class TestBuildSearchQueries:
    def test_returns_description_plus_keywords(self) -> None:
        queries = _build_search_queries("implement context injection pipeline")
        assert len(queries) >= 2
        assert queries[0] == "implement context injection pipeline"

    def test_empty_description(self) -> None:
        queries = _build_search_queries("")
        assert len(queries) == 1


class TestDeduplicateSnippets:
    def test_removes_duplicates(self) -> None:
        s1 = ContextSnippet(file_path="a.py", content="x", start_line=1)
        s2 = ContextSnippet(file_path="a.py", content="y", start_line=1)
        s3 = ContextSnippet(file_path="a.py", content="z", start_line=5)
        result = _deduplicate_snippets([s1, s2, s3])
        assert len(result) == 2
        assert result[0].content == "x"
        assert result[1].content == "z"


class TestRankSnippets:
    def test_boosts_keyword_matches(self) -> None:
        s1 = ContextSnippet(file_path="foo.py", content="unrelated code here", score=0.8)
        s2 = ContextSnippet(
            file_path="context/injection.py", content="context injection pipeline", score=0.5
        )
        ranked = _rank_snippets([s1, s2], "context injection pipeline")
        # s2 has 3 keyword matches in content + 2 path matches, should outrank s1
        assert ranked[0].file_path == "context/injection.py"

    def test_preserves_score_order_without_keywords(self) -> None:
        s1 = ContextSnippet(file_path="a.py", content="x", score=0.9)
        s2 = ContextSnippet(file_path="b.py", content="y", score=0.5)
        ranked = _rank_snippets([s1, s2], "")
        assert ranked[0].score == 0.9


class TestTrimToBudget:
    def test_trims_over_budget(self) -> None:
        budget = ContextBudget(max_tokens=100, reserved_for_system=0, reserved_for_user=0)
        # Each snippet ~25 tokens (100 chars / 4)
        snippets = [
            ContextSnippet(file_path="a.py", content="x" * 100, token_estimate=25),
            ContextSnippet(file_path="b.py", content="y" * 100, token_estimate=25),
            ContextSnippet(file_path="c.py", content="z" * 100, token_estimate=25),
            ContextSnippet(file_path="d.py", content="w" * 100, token_estimate=25),
            ContextSnippet(file_path="e.py", content="v" * 100, token_estimate=25),
        ]
        kept, trimmed = _trim_to_budget(snippets, budget)
        assert len(kept) == 4
        assert trimmed == 1

    def test_keeps_all_within_budget(self) -> None:
        budget = ContextBudget(max_tokens=1000, reserved_for_system=0, reserved_for_user=0)
        snippets = [
            ContextSnippet(file_path="a.py", content="x" * 100, token_estimate=25),
        ]
        kept, trimmed = _trim_to_budget(snippets, budget)
        assert len(kept) == 1
        assert trimmed == 0


# ---------------------------------------------------------------------------
# Types tests
# ---------------------------------------------------------------------------


class TestContextBudget:
    def test_available_tokens(self) -> None:
        b = ContextBudget(max_tokens=10000, reserved_for_system=1000, reserved_for_user=1000)
        assert b.available_tokens == 8000

    def test_available_tokens_clamped(self) -> None:
        b = ContextBudget(max_tokens=100, reserved_for_system=500, reserved_for_user=500)
        assert b.available_tokens == 0


class TestInjectedContext:
    def test_as_prompt_section_empty(self) -> None:
        ctx = InjectedContext()
        assert ctx.as_prompt_section == ""

    def test_as_prompt_section_with_snippets(self) -> None:
        ctx = InjectedContext(
            snippets=(
                ContextSnippet(
                    file_path="src/foo.py",
                    content="def foo(): pass",
                    language="python",
                    start_line=10,
                    end_line=11,
                ),
            ),
            file_paths=("src/foo.py",),
            architectural_summary="Found 1 relevant file(s)",
            trimmed_count=2,
        )
        prompt = ctx.as_prompt_section
        assert "src/foo.py" in prompt
        assert "def foo(): pass" in prompt
        assert "```python" in prompt
        assert "(L10-11)" in prompt
        assert "2 additional snippet(s) omitted" in prompt
        assert "Architectural Context" in prompt


# ---------------------------------------------------------------------------
# Integration tests for ContextInjector
# ---------------------------------------------------------------------------


class TestContextInjector:
    @pytest.fixture()
    def searcher(self) -> FakeCodebaseIndexSearcher:
        s = FakeCodebaseIndexSearcher()
        s.indices = [
            {"index_id": "idx-1", "project_id": "proj-1"},
        ]
        s.entries = [
            {
                "index_id": "idx-1",
                "file_path": "src/injector.py",
                "content": "class ContextInjector:\n    def gather_context(self): ...",
                "language": "python",
                "start_line": 1,
                "end_line": 2,
            },
            {
                "index_id": "idx-1",
                "file_path": "src/types.py",
                "content": "class ContextSnippet:\n    file_path: str",
                "language": "python",
                "start_line": 1,
                "end_line": 2,
            },
            {
                "index_id": "idx-1",
                "file_path": "src/unrelated.py",
                "content": "def hello_world(): print('hello')",
                "language": "python",
                "start_line": 1,
                "end_line": 1,
            },
        ]
        return s

    async def test_gather_context_returns_relevant_snippets(
        self, searcher: FakeCodebaseIndexSearcher
    ) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("proj-1", "implement ContextInjector service")
        assert isinstance(result, InjectedContext)
        assert len(result.snippets) > 0
        # Should find the injector file
        paths = [s.file_path for s in result.snippets]
        assert "src/injector.py" in paths

    async def test_gather_context_no_indices(self, searcher: FakeCodebaseIndexSearcher) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("nonexistent", "anything")
        assert len(result.snippets) == 0
        assert result.as_prompt_section == ""

    async def test_gather_context_no_results(self, searcher: FakeCodebaseIndexSearcher) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("proj-1", "xyzzynotfound")
        assert len(result.snippets) == 0

    async def test_gather_context_respects_budget(
        self, searcher: FakeCodebaseIndexSearcher
    ) -> None:
        # Very tight budget
        budget = ContextBudget(max_tokens=20, reserved_for_system=0, reserved_for_user=0)
        injector = ContextInjector(searcher, budget=budget)
        result = await injector.gather_context("proj-1", "ContextInjector")
        # Should trim some snippets
        assert result.total_tokens <= 20

    async def test_gather_context_budget_override(
        self, searcher: FakeCodebaseIndexSearcher
    ) -> None:
        injector = ContextInjector(searcher)
        tiny_budget = ContextBudget(max_tokens=10, reserved_for_system=0, reserved_for_user=0)
        result = await injector.gather_context("proj-1", "ContextInjector", budget=tiny_budget)
        assert result.total_tokens <= 10

    async def test_gather_context_deduplicates(self, searcher: FakeCodebaseIndexSearcher) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("proj-1", "ContextInjector")
        # Even though multiple queries may hit same entry, should be deduplicated
        paths_and_lines = [(s.file_path, s.start_line) for s in result.snippets]
        assert len(paths_and_lines) == len(set(paths_and_lines))

    async def test_gather_context_file_paths_unique(
        self, searcher: FakeCodebaseIndexSearcher
    ) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("proj-1", "ContextInjector")
        assert len(result.file_paths) == len(set(result.file_paths))

    async def test_gather_context_as_prompt_section(
        self, searcher: FakeCodebaseIndexSearcher
    ) -> None:
        injector = ContextInjector(searcher)
        result = await injector.gather_context("proj-1", "ContextInjector")
        prompt = result.as_prompt_section
        if result.snippets:
            assert "```" in prompt
            assert "Relevant Files" in prompt

    async def test_searcher_protocol_compliance(self) -> None:
        """Verify FakeCodebaseIndexSearcher satisfies the protocol."""
        from lintel.context_injection.injector import CodebaseIndexSearcher

        assert isinstance(FakeCodebaseIndexSearcher(), CodebaseIndexSearcher)
