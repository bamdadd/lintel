"""Tests for review score store."""

from __future__ import annotations

from lintel.review_scores_api.store import ReviewScoreStore


async def test_add_and_get() -> None:
    store = ReviewScoreStore()
    await store.add(
        {
            "score_id": "s1",
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.5,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    )
    result = await store.get("s1")
    assert result is not None
    assert result["dimension"] == "security"


async def test_get_trend_by_repo() -> None:
    store = ReviewScoreStore()
    await store.add(
        {
            "score_id": "s1",
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.5,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    )
    await store.add(
        {
            "score_id": "s2",
            "repo_id": "repo-1",
            "dimension": "correctness",
            "score": 8.0,
            "recorded_at": "2026-01-02T00:00:00Z",
        }
    )
    await store.add(
        {
            "score_id": "s3",
            "repo_id": "repo-2",
            "dimension": "security",
            "score": 6.0,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    )

    results = await store.get_trend_by_repo("repo-1")
    assert len(results) == 2

    results = await store.get_trend_by_repo("repo-1", dimension="security")
    assert len(results) == 1
    assert results[0]["score_id"] == "s1"


async def test_get_trend_by_contributor() -> None:
    store = ReviewScoreStore()
    await store.add(
        {
            "score_id": "s1",
            "repo_id": "repo-1",
            "contributor_id": "user-1",
            "dimension": "security",
            "score": 7.5,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    )
    results = await store.get_trend_by_contributor("user-1")
    assert len(results) == 1

    results = await store.get_trend_by_contributor("nonexistent")
    assert len(results) == 0
