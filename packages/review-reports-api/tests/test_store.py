"""Tests for review report store."""

from __future__ import annotations

from lintel.review_reports_api.store import ReviewReportStore


async def test_add_and_get() -> None:
    store = ReviewReportStore()
    await store.add({"report_id": "r1", "repo_id": "repo-1", "pipeline_run_id": "run-1"})
    result = await store.get("r1")
    assert result is not None
    assert result["repo_id"] == "repo-1"


async def test_get_missing() -> None:
    store = ReviewReportStore()
    assert await store.get("nonexistent") is None


async def test_list_by_repo() -> None:
    store = ReviewReportStore()
    await store.add({"report_id": "r1", "repo_id": "repo-1", "pipeline_run_id": "run-1"})
    await store.add({"report_id": "r2", "repo_id": "repo-2", "pipeline_run_id": "run-2"})
    results = await store.list_by_repo("repo-1")
    assert len(results) == 1
    assert results[0]["report_id"] == "r1"


async def test_list_by_pipeline_run() -> None:
    store = ReviewReportStore()
    await store.add({"report_id": "r1", "repo_id": "repo-1", "pipeline_run_id": "run-1"})
    await store.add({"report_id": "r2", "repo_id": "repo-2", "pipeline_run_id": "run-1"})
    results = await store.list_by_pipeline_run("run-1")
    assert len(results) == 2


async def test_remove() -> None:
    store = ReviewReportStore()
    await store.add({"report_id": "r1", "repo_id": "repo-1", "pipeline_run_id": "run-1"})
    assert await store.remove("r1") is True
    assert await store.get("r1") is None
    assert await store.remove("r1") is False
