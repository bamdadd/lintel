"""Tests for post-test quality gate evaluation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes._post_test_gates import (
    evaluate_quality_gates,
    has_blocking_failures,
)


def _make_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.append_log = AsyncMock()
    return tracker


def _make_rule_store(rules: list[dict[str, Any]]) -> AsyncMock:
    store = AsyncMock()
    store.list_by_project = AsyncMock(return_value=rules)
    return store


def _make_coverage_store(prev: dict[str, Any] | None = None) -> AsyncMock:
    store = AsyncMock()
    store.get_latest_by_project = AsyncMock(return_value=prev)
    return store


class TestEvaluateQualityGates:
    async def test_no_rules_returns_empty(self) -> None:
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=None,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store([]),
        )
        assert results == []

    async def test_no_store_returns_empty(self) -> None:
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=None,
            tracker=_make_tracker(),
            quality_gate_rule_store=None,
        )
        assert results == []

    async def test_min_pass_rate_passes(self) -> None:
        rules = [
            {
                "rule_id": "r1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 80.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=1,
            coverage_line_rate=None,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert len(results) == 1
        assert results[0]["passed"] is True

    async def test_min_pass_rate_fails(self) -> None:
        rules = [
            {
                "rule_id": "r1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 90.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=False,
            test_total=10,
            test_failures=5,
            coverage_line_rate=None,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert len(results) == 1
        assert results[0]["passed"] is False
        assert results[0]["severity"] == "error"

    async def test_min_coverage_passes(self) -> None:
        rules = [
            {
                "rule_id": "r2",
                "project_id": "proj-1",
                "rule_type": "min_coverage",
                "threshold": 70.0,
                "severity": "warn",
                "enabled": True,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=0.85,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert len(results) == 1
        assert results[0]["passed"] is True

    async def test_min_coverage_fails(self) -> None:
        rules = [
            {
                "rule_id": "r2",
                "project_id": "proj-1",
                "rule_type": "min_coverage",
                "threshold": 80.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=0.50,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert len(results) == 1
        assert results[0]["passed"] is False

    async def test_coverage_drop_with_previous(self) -> None:
        rules = [
            {
                "rule_id": "r3",
                "project_id": "proj-1",
                "rule_type": "max_coverage_drop",
                "threshold": 5.0,
                "severity": "warn",
                "enabled": True,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=0.70,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
            coverage_metric_store=_make_coverage_store({"line_rate": 0.85}),
        )
        assert len(results) == 1
        assert results[0]["passed"] is False  # Drop of 15pp > 5pp threshold

    async def test_disabled_rules_skipped(self) -> None:
        rules = [
            {
                "rule_id": "r1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 100.0,
                "severity": "error",
                "enabled": False,
            }
        ]
        results = await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=5,
            coverage_line_rate=None,
            tracker=_make_tracker(),
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert results == []

    async def test_logs_to_tracker(self) -> None:
        rules = [
            {
                "rule_id": "r1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 80.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        tracker = _make_tracker()
        await evaluate_quality_gates(
            project_id="proj-1",
            run_id="run-1",
            test_passed=True,
            test_total=10,
            test_failures=0,
            coverage_line_rate=None,
            tracker=tracker,
            quality_gate_rule_store=_make_rule_store(rules),
        )
        assert tracker.append_log.call_count > 0


class TestHasBlockingFailures:
    def test_no_failures(self) -> None:
        results = [{"passed": True, "severity": "error"}]
        assert has_blocking_failures(results) is False

    def test_warn_failure_not_blocking(self) -> None:
        results = [{"passed": False, "severity": "warn"}]
        assert has_blocking_failures(results) is False

    def test_error_failure_blocking(self) -> None:
        results = [{"passed": False, "severity": "error"}]
        assert has_blocking_failures(results) is True

    def test_empty_results(self) -> None:
        assert has_blocking_failures([]) is False
