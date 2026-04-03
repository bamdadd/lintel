"""ContextInjector — queries codebase index and builds ranked context for agents."""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

import structlog

from lintel.context_injection.types import ContextBudget, ContextSnippet, InjectedContext

logger = structlog.get_logger()

# Rough token estimate: ~4 chars per token for code
CHARS_PER_TOKEN = 4


@runtime_checkable
class CodebaseIndexSearcher(Protocol):
    """Protocol for searching a codebase index."""

    async def search(self, index_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]: ...

    async def list_indices_by_project(self, project_id: str) -> list[dict[str, Any]]: ...


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (~4 chars per token for code)."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _extract_keywords(description: str) -> list[str]:
    """Extract meaningful keywords from a work item description."""
    stop_words = frozenset(
        {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "need",
            "must",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
            "we",
            "our",
            "you",
            "your",
            "they",
            "their",
            "he",
            "she",
            "his",
            "her",
            "not",
            "no",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "than",
            "too",
            "very",
            "just",
            "also",
            "as",
            "if",
            "so",
            "up",
            "out",
            "about",
            "into",
            "over",
            "after",
            "before",
        }
    )
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", description.lower())
    return [w for w in words if w not in stop_words and len(w) > 2]


def _build_search_queries(description: str) -> list[str]:
    """Build multiple search queries from a description for broader coverage."""
    keywords = _extract_keywords(description)
    if not keywords:
        return [description[:200]]

    queries: list[str] = []
    # Full description as first query (truncated)
    queries.append(description[:200])
    # Top keywords as individual queries
    for kw in keywords[:5]:
        queries.append(kw)
    return queries


def _rank_snippets(snippets: list[ContextSnippet], description: str) -> list[ContextSnippet]:
    """Re-rank snippets by relevance to the description."""
    keywords = set(_extract_keywords(description))
    if not keywords:
        return sorted(snippets, key=lambda s: s.score, reverse=True)

    scored: list[tuple[float, ContextSnippet]] = []
    for snippet in snippets:
        content_lower = snippet.content.lower()
        path_lower = snippet.file_path.lower()
        # Base score from search
        score = snippet.score
        # Boost for keyword matches in content
        keyword_hits = sum(1 for kw in keywords if kw in content_lower)
        score += keyword_hits * 0.2
        # Boost for keyword matches in file path
        path_hits = sum(1 for kw in keywords if kw in path_lower)
        score += path_hits * 0.3
        scored.append((score, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]


def _deduplicate_snippets(snippets: list[ContextSnippet]) -> list[ContextSnippet]:
    """Remove duplicate snippets (same file_path + start_line)."""
    seen: set[tuple[str, int]] = set()
    result: list[ContextSnippet] = []
    for s in snippets:
        key = (s.file_path, s.start_line)
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _trim_to_budget(
    snippets: list[ContextSnippet], budget: ContextBudget
) -> tuple[list[ContextSnippet], int]:
    """Trim snippets to fit within the token budget. Returns (kept, trimmed_count)."""
    available = budget.available_tokens
    kept: list[ContextSnippet] = []
    used = 0
    trimmed = 0

    for snippet in snippets:
        tokens = snippet.token_estimate or estimate_tokens(snippet.content)
        if used + tokens > available:
            trimmed += 1
            continue
        kept.append(snippet)
        used += tokens

    return kept, trimmed


class ContextInjector:
    """Queries codebase index and builds ranked, budget-aware context for agents."""

    def __init__(
        self,
        searcher: CodebaseIndexSearcher,
        budget: ContextBudget | None = None,
    ) -> None:
        self._searcher = searcher
        self._budget = budget or ContextBudget()

    async def gather_context(
        self,
        project_id: str,
        description: str,
        budget: ContextBudget | None = None,
    ) -> InjectedContext:
        """Query the codebase index and return ranked, trimmed context.

        Args:
            project_id: The project whose codebase indices to search.
            description: Work item or task description to search for.
            budget: Optional override for the default token budget.

        Returns:
            InjectedContext with ranked snippets, file paths, and summary.
        """
        effective_budget = budget or self._budget

        # Find indices for this project
        indices = await self._searcher.list_indices_by_project(project_id)
        if not indices:
            logger.info("context_injection_no_indices", project_id=project_id)
            return InjectedContext()

        # Search across all indices with multiple queries
        queries = _build_search_queries(description)
        all_results: list[dict[str, Any]] = []

        for index in indices:
            index_id = index.get("index_id", "")
            if not index_id:
                continue
            for query in queries:
                try:
                    results = await self._searcher.search(index_id, query, limit=10)
                    all_results.extend(results)
                except Exception:
                    logger.warning(
                        "context_injection_search_failed",
                        index_id=index_id,
                        query=query[:50],
                    )

        if not all_results:
            logger.info(
                "context_injection_no_results",
                project_id=project_id,
                query_count=len(queries),
            )
            return InjectedContext()

        # Convert to ContextSnippet
        snippets = [
            ContextSnippet(
                file_path=r.get("file_path", ""),
                content=r.get("content", ""),
                score=float(r.get("score", 0.0)),
                language=r.get("language", ""),
                start_line=int(r.get("start_line", 0)),
                end_line=int(r.get("end_line", 0)),
                token_estimate=estimate_tokens(r.get("content", "")),
            )
            for r in all_results
            if r.get("content")
        ]

        # Deduplicate, rank, and trim
        snippets = _deduplicate_snippets(snippets)
        snippets = _rank_snippets(snippets, description)
        kept, trimmed_count = _trim_to_budget(snippets, effective_budget)

        # Extract unique file paths (preserving rank order)
        seen_paths: set[str] = set()
        file_paths: list[str] = []
        for s in kept:
            if s.file_path and s.file_path not in seen_paths:
                seen_paths.add(s.file_path)
                file_paths.append(s.file_path)

        total_tokens = sum(s.token_estimate or estimate_tokens(s.content) for s in kept)

        # Build architectural summary from top snippets
        arch_summary = _build_architectural_summary(kept, description)

        logger.info(
            "context_injection_complete",
            project_id=project_id,
            snippets_found=len(snippets) + trimmed_count,
            snippets_kept=len(kept),
            trimmed=trimmed_count,
            total_tokens=total_tokens,
            file_count=len(file_paths),
        )

        return InjectedContext(
            snippets=tuple(kept),
            file_paths=tuple(file_paths),
            architectural_summary=arch_summary,
            total_tokens=total_tokens,
            trimmed_count=trimmed_count,
        )


def _build_architectural_summary(snippets: list[ContextSnippet], description: str) -> str:
    """Build a brief architectural summary from the top snippets."""
    if not snippets:
        return ""

    unique_files = []
    seen: set[str] = set()
    for s in snippets[:10]:
        if s.file_path not in seen:
            seen.add(s.file_path)
            unique_files.append(s.file_path)

    if not unique_files:
        return ""

    lines = [f"Found {len(unique_files)} relevant file(s) for: {description[:100]}"]
    for fp in unique_files[:5]:
        lines.append(f"- `{fp}`")
    if len(unique_files) > 5:
        lines.append(f"- ... and {len(unique_files) - 5} more")
    return "\n".join(lines)
