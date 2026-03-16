"""Tests for REQ-010 stores (ParsedTestResultStore, CoverageMetricStore, QualityGateRuleStore)."""

from __future__ import annotations

from lintel.artifacts_api.store import (
    CoverageMetricStore,
    ParsedTestResultStore,
    QualityGateRuleStore,
)


class TestParsedTestResultStore:
    async def test_save_and_get(self) -> None:
        store = ParsedTestResultStore()
        record = await store.save(
            result_id="r1",
            run_id="run-1",
            project_id="proj-1",
            artifact_id="art-1",
            data={"total": 10, "passed": 8, "failed": 2},
        )
        assert record["result_id"] == "r1"
        assert record["total"] == 10

        fetched = await store.get("r1")
        assert fetched is not None
        assert fetched["run_id"] == "run-1"

    async def test_get_returns_none_for_missing(self) -> None:
        store = ParsedTestResultStore()
        assert await store.get("missing") is None

    async def test_get_by_run(self) -> None:
        store = ParsedTestResultStore()
        await store.save("r1", "run-1", "proj-1", "art-1", {"total": 5})
        await store.save("r2", "run-1", "proj-1", "art-2", {"total": 3})
        await store.save("r3", "run-2", "proj-1", "art-3", {"total": 7})

        results = await store.get_by_run("run-1")
        assert len(results) == 2
        assert all(r["run_id"] == "run-1" for r in results)

    async def test_get_by_run_returns_empty_for_missing(self) -> None:
        store = ParsedTestResultStore()
        assert await store.get_by_run("no-run") == []


class TestCoverageMetricStore:
    async def test_save_and_get_by_run(self) -> None:
        store = CoverageMetricStore()
        await store.save(
            metric_id="m1",
            run_id="run-1",
            project_id="proj-1",
            artifact_id="art-1",
            data={"line_rate": 0.85, "branch_rate": 0.72},
        )
        result = await store.get_by_run("run-1")
        assert result is not None
        assert result["line_rate"] == 0.85

    async def test_get_by_run_returns_none_for_missing(self) -> None:
        store = CoverageMetricStore()
        assert await store.get_by_run("no-run") is None

    async def test_get_latest_by_project(self) -> None:
        store = CoverageMetricStore()
        await store.save("m1", "run-1", "proj-1", "art-1", {"line_rate": 0.80})
        await store.save("m2", "run-2", "proj-1", "art-2", {"line_rate": 0.85})

        latest = await store.get_latest_by_project("proj-1")
        assert latest is not None
        assert latest["line_rate"] == 0.85

    async def test_get_latest_by_project_returns_none_for_missing(self) -> None:
        store = CoverageMetricStore()
        assert await store.get_latest_by_project("no-proj") is None


class TestQualityGateRuleStore:
    async def test_add_and_get(self) -> None:
        store = QualityGateRuleStore()
        rule = {
            "rule_id": "qr1",
            "project_id": "proj-1",
            "rule_type": "min_coverage",
            "threshold": 80.0,
        }
        await store.add(rule)
        fetched = await store.get("qr1")
        assert fetched is not None
        assert fetched["threshold"] == 80.0

    async def test_get_returns_none_for_missing(self) -> None:
        store = QualityGateRuleStore()
        assert await store.get("missing") is None

    async def test_list_by_project(self) -> None:
        store = QualityGateRuleStore()
        await store.add({"rule_id": "r1", "project_id": "proj-1", "rule_type": "min_coverage"})
        await store.add({"rule_id": "r2", "project_id": "proj-1", "rule_type": "min_pass_rate"})
        await store.add({"rule_id": "r3", "project_id": "proj-2", "rule_type": "min_coverage"})

        rules = await store.list_by_project("proj-1")
        assert len(rules) == 2
        assert all(r["project_id"] == "proj-1" for r in rules)

    async def test_update(self) -> None:
        store = QualityGateRuleStore()
        await store.add({"rule_id": "r1", "project_id": "proj-1", "threshold": 80.0})
        updated = await store.update("r1", {"threshold": 90.0})
        assert updated is not None
        assert updated["threshold"] == 90.0

    async def test_update_returns_none_for_missing(self) -> None:
        store = QualityGateRuleStore()
        assert await store.update("missing", {"threshold": 90.0}) is None

    async def test_remove(self) -> None:
        store = QualityGateRuleStore()
        await store.add({"rule_id": "r1", "project_id": "proj-1"})
        assert await store.remove("r1") is True
        assert await store.get("r1") is None

    async def test_remove_returns_false_for_missing(self) -> None:
        store = QualityGateRuleStore()
        assert await store.remove("missing") is False
