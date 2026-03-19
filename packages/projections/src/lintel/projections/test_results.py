"""Test results and coverage projection (REQ-010).

Maintains in-memory read models for parsed test results,
coverage metrics, and quality gate evaluation outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


@dataclass
class TestResultRecord:
    """Read model for a parsed test result."""

    run_id: str
    project_id: str
    artifact_id: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    duration_ms: int = 0
    quality_gate_status: str = "pending"
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )


@dataclass
class CoverageMetricRecord:
    """Read model for a coverage measurement."""

    run_id: str
    project_id: str
    artifact_id: str
    line_rate: float = 0.0
    branch_rate: float = 0.0
    quality_gate_status: str = "pending"
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )


class TestResultsProjection:
    """Builds read models from test result and quality gate events."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "TestResultsParsed",
            "CoverageMeasured",
            "QualityGateEvaluated",
        }
    )

    def __init__(self) -> None:
        self._test_results: dict[str, TestResultRecord] = {}
        self._coverage_metrics: dict[str, CoverageMetricRecord] = {}

    @property
    def name(self) -> str:
        return "test_results"

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    def get_state(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "test_results": {k: asdict(v) for k, v in self._test_results.items()},
            "coverage_metrics": {k: asdict(v) for k, v in self._coverage_metrics.items()},
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        def _parse_dt(v: str | datetime) -> datetime:
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        self._test_results = {
            k: TestResultRecord(
                run_id=v["run_id"],
                project_id=v["project_id"],
                artifact_id=v["artifact_id"],
                total=v.get("total", 0),
                passed=v.get("passed", 0),
                failed=v.get("failed", 0),
                errors=v.get("errors", 0),
                skipped=v.get("skipped", 0),
                pass_rate=v.get("pass_rate", 0.0),
                duration_ms=v.get("duration_ms", 0),
                quality_gate_status=v.get(
                    "quality_gate_status",
                    "pending",
                ),
                occurred_at=_parse_dt(
                    v.get("occurred_at", datetime.now(UTC)),
                ),
            )
            for k, v in state.get("test_results", {}).items()
        }
        self._coverage_metrics = {
            k: CoverageMetricRecord(
                run_id=v["run_id"],
                project_id=v["project_id"],
                artifact_id=v["artifact_id"],
                line_rate=v.get("line_rate", 0.0),
                branch_rate=v.get("branch_rate", 0.0),
                quality_gate_status=v.get(
                    "quality_gate_status",
                    "pending",
                ),
                occurred_at=_parse_dt(
                    v.get("occurred_at", datetime.now(UTC)),
                ),
            )
            for k, v in state.get("coverage_metrics", {}).items()
        }

    async def project(self, event: EventEnvelope) -> None:
        handler = _HANDLERS.get(event.event_type)
        if handler:
            handler(self, event)

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._test_results.clear()
        self._coverage_metrics.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    # -- Event handlers ---

    def _on_test_results_parsed(
        self,
        event: EventEnvelope,
    ) -> None:
        payload = event.payload
        run_id = payload.get("run_id", "")
        self._test_results[run_id] = TestResultRecord(
            run_id=run_id,
            project_id=payload.get("project_id", ""),
            artifact_id=payload.get("artifact_id", ""),
            total=int(payload.get("total", 0)),
            passed=int(payload.get("passed", 0)),
            failed=int(payload.get("failed", 0)),
            errors=int(payload.get("errors", 0)),
            skipped=int(payload.get("skipped", 0)),
            pass_rate=float(payload.get("pass_rate", 0.0)),
            duration_ms=int(payload.get("duration_ms", 0)),
            occurred_at=event.occurred_at,
        )

    def _on_coverage_measured(
        self,
        event: EventEnvelope,
    ) -> None:
        payload = event.payload
        run_id = payload.get("run_id", "")
        self._coverage_metrics[run_id] = CoverageMetricRecord(
            run_id=run_id,
            project_id=payload.get("project_id", ""),
            artifact_id=payload.get("artifact_id", ""),
            line_rate=float(payload.get("line_rate", 0.0)),
            branch_rate=float(payload.get("branch_rate", 0.0)),
            occurred_at=event.occurred_at,
        )

    def _on_quality_gate_evaluated(
        self,
        event: EventEnvelope,
    ) -> None:
        payload = event.payload
        run_id = payload.get("run_id", "")
        passed = payload.get("passed", True)
        status = "passed" if passed else "failed"

        if run_id in self._test_results:
            self._test_results[run_id].quality_gate_status = status
        if run_id in self._coverage_metrics:
            self._coverage_metrics[run_id].quality_gate_status = status

    # -- Query helpers ---

    def get_test_results(
        self,
        run_id: str,
    ) -> TestResultRecord | None:
        return self._test_results.get(run_id)

    def get_coverage(
        self,
        run_id: str,
    ) -> CoverageMetricRecord | None:
        return self._coverage_metrics.get(run_id)

    def get_summary(self, run_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"run_id": run_id}
        tr = self._test_results.get(run_id)
        if tr:
            from dataclasses import asdict

            result["test_results"] = asdict(tr)
        cm = self._coverage_metrics.get(run_id)
        if cm:
            from dataclasses import asdict

            result["coverage"] = asdict(cm)
        return result


_HANDLERS: dict[str, Any] = {
    "TestResultsParsed": (TestResultsProjection._on_test_results_parsed),
    "CoverageMeasured": (TestResultsProjection._on_coverage_measured),
    "QualityGateEvaluated": (TestResultsProjection._on_quality_gate_evaluated),
}
