"""Tests for TestResultsProjection (REQ-010)."""

from __future__ import annotations

from lintel.domain.events import CoverageMeasured, QualityGateEvaluated, TestResultsParsed
from lintel.projections.test_results import TestResultsProjection


class TestTestResultsProjection:
    async def test_handles_expected_event_types(self) -> None:
        proj = TestResultsProjection()
        assert "TestResultsParsed" in proj.handled_event_types
        assert "CoverageMeasured" in proj.handled_event_types
        assert "QualityGateEvaluated" in proj.handled_event_types

    async def test_project_test_results_parsed(self) -> None:
        proj = TestResultsProjection()
        event = TestResultsParsed(
            payload={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_id": "art-1",
                "total": 10,
                "passed": 8,
                "failed": 2,
                "pass_rate": 80.0,
            }
        )
        await proj.project(event)

        record = proj.get_test_results("run-1")
        assert record is not None
        assert record.total == 10
        assert record.passed == 8
        assert record.failed == 2
        assert record.pass_rate == 80.0
        assert record.quality_gate_status == "pending"

    async def test_project_coverage_measured(self) -> None:
        proj = TestResultsProjection()
        event = CoverageMeasured(
            payload={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_id": "art-1",
                "line_rate": 0.85,
                "branch_rate": 0.72,
            }
        )
        await proj.project(event)

        record = proj.get_coverage("run-1")
        assert record is not None
        assert record.line_rate == 0.85
        assert record.branch_rate == 0.72
        assert record.quality_gate_status == "pending"

    async def test_quality_gate_updates_test_result_status(self) -> None:
        proj = TestResultsProjection()
        await proj.project(
            TestResultsParsed(
                payload={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_id": "art-1",
                    "total": 10,
                    "passed": 10,
                }
            )
        )
        await proj.project(
            QualityGateEvaluated(
                payload={
                    "run_id": "run-1",
                    "passed": True,
                }
            )
        )

        record = proj.get_test_results("run-1")
        assert record is not None
        assert record.quality_gate_status == "passed"

    async def test_quality_gate_failure_updates_status(self) -> None:
        proj = TestResultsProjection()
        await proj.project(
            CoverageMeasured(
                payload={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_id": "art-1",
                    "line_rate": 0.50,
                }
            )
        )
        await proj.project(
            QualityGateEvaluated(
                payload={
                    "run_id": "run-1",
                    "passed": False,
                }
            )
        )

        record = proj.get_coverage("run-1")
        assert record is not None
        assert record.quality_gate_status == "failed"

    async def test_get_summary_combines_results_and_coverage(self) -> None:
        proj = TestResultsProjection()
        await proj.project(
            TestResultsParsed(
                payload={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_id": "art-1",
                    "total": 5,
                    "passed": 5,
                }
            )
        )
        await proj.project(
            CoverageMeasured(
                payload={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_id": "art-2",
                    "line_rate": 0.90,
                }
            )
        )

        summary = proj.get_summary("run-1")
        assert "test_results" in summary
        assert "coverage" in summary
        assert summary["test_results"]["total"] == 5
        assert summary["coverage"]["line_rate"] == 0.90

    async def test_get_summary_empty_for_unknown_run(self) -> None:
        proj = TestResultsProjection()
        summary = proj.get_summary("unknown")
        assert summary == {"run_id": "unknown"}

    async def test_rebuild_clears_and_replays(self) -> None:
        proj = TestResultsProjection()
        # Initial state
        await proj.project(
            TestResultsParsed(
                payload={
                    "run_id": "run-old",
                    "project_id": "proj-1",
                    "artifact_id": "art-1",
                    "total": 1,
                }
            )
        )
        assert proj.get_test_results("run-old") is not None

        # Rebuild with different events
        events = [
            TestResultsParsed(
                payload={
                    "run_id": "run-new",
                    "project_id": "proj-1",
                    "artifact_id": "art-2",
                    "total": 20,
                    "passed": 18,
                }
            ),
            CoverageMeasured(
                payload={
                    "run_id": "run-new",
                    "project_id": "proj-1",
                    "artifact_id": "art-3",
                    "line_rate": 0.95,
                }
            ),
        ]
        await proj.rebuild(events)

        # Old state cleared
        assert proj.get_test_results("run-old") is None
        # New state present
        record = proj.get_test_results("run-new")
        assert record is not None
        assert record.total == 20

    async def test_get_state_and_restore_state(self) -> None:
        proj = TestResultsProjection()
        await proj.project(
            TestResultsParsed(
                payload={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_id": "art-1",
                    "total": 10,
                    "passed": 9,
                }
            )
        )

        state = proj.get_state()

        # Restore into a fresh projection
        proj2 = TestResultsProjection()
        proj2.restore_state(state)

        record = proj2.get_test_results("run-1")
        assert record is not None
        assert record.total == 10
        assert record.passed == 9
