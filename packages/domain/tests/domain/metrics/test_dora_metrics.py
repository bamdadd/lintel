"""Tests for DORA metrics collector and classification helpers."""

from __future__ import annotations

from lintel.domain.metrics.dora_metrics import (
    DORALevel,
    DORAMetrics,
    DORAMetricsCollector,
    PipelineRunRecord,
    classify_change_failure_rate,
    classify_deploy_frequency,
    classify_lead_time,
    classify_mttr,
)

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


class TestClassifyDeployFrequency:
    def test_elite(self) -> None:
        assert classify_deploy_frequency(2.0) == DORALevel.ELITE

    def test_high(self) -> None:
        assert classify_deploy_frequency(0.5) == DORALevel.HIGH

    def test_medium(self) -> None:
        assert classify_deploy_frequency(1.0 / 14) == DORALevel.MEDIUM

    def test_low(self) -> None:
        assert classify_deploy_frequency(1.0 / 60) == DORALevel.LOW


class TestClassifyLeadTime:
    def test_elite(self) -> None:
        assert classify_lead_time(1800) == DORALevel.ELITE  # 30 min

    def test_high(self) -> None:
        assert classify_lead_time(86400) == DORALevel.HIGH  # 1 day

    def test_medium(self) -> None:
        assert classify_lead_time(1_209_600) == DORALevel.MEDIUM  # 14 days

    def test_low(self) -> None:
        assert classify_lead_time(5_000_000) == DORALevel.LOW


class TestClassifyChangeFailureRate:
    def test_elite(self) -> None:
        assert classify_change_failure_rate(0.03) == DORALevel.ELITE

    def test_high(self) -> None:
        assert classify_change_failure_rate(0.08) == DORALevel.HIGH

    def test_medium(self) -> None:
        assert classify_change_failure_rate(0.12) == DORALevel.MEDIUM

    def test_low(self) -> None:
        assert classify_change_failure_rate(0.25) == DORALevel.LOW


class TestClassifyMTTR:
    def test_elite(self) -> None:
        assert classify_mttr(1800) == DORALevel.ELITE

    def test_high(self) -> None:
        assert classify_mttr(43200) == DORALevel.HIGH  # 12 hours

    def test_medium(self) -> None:
        assert classify_mttr(259200) == DORALevel.MEDIUM  # 3 days

    def test_low(self) -> None:
        assert classify_mttr(700_000) == DORALevel.LOW


# ---------------------------------------------------------------------------
# DORAMetrics dataclass properties
# ---------------------------------------------------------------------------


class TestDORAMetricsProperties:
    def test_level_properties(self) -> None:
        m = DORAMetrics(
            deploy_frequency=2.0,
            lead_time_seconds=1800,
            change_failure_rate=0.03,
            mean_time_to_restore_seconds=1800,
        )
        assert m.deploy_frequency_level == DORALevel.ELITE
        assert m.lead_time_level == DORALevel.ELITE
        assert m.change_failure_rate_level == DORALevel.ELITE
        assert m.mttr_level == DORALevel.ELITE


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

_BASE = 1_700_000_000.0  # arbitrary epoch base


def _record(
    run_id: str,
    project_id: str = "proj-1",
    *,
    start_offset: float = 0,
    duration: float = 3600,
    succeeded: bool = True,
) -> PipelineRunRecord:
    return PipelineRunRecord(
        run_id=run_id,
        project_id=project_id,
        started_at=_BASE + start_offset,
        finished_at=_BASE + start_offset + duration,
        succeeded=succeeded,
    )


class TestDORAMetricsCollector:
    def test_empty_collector_returns_zeros(self) -> None:
        c = DORAMetricsCollector()
        m = c.compute()
        assert m.deploy_frequency == 0.0
        assert m.lead_time_seconds == 0.0
        assert m.change_failure_rate == 0.0
        assert m.mean_time_to_restore_seconds == 0.0

    def test_deploy_frequency(self) -> None:
        c = DORAMetricsCollector()
        # 3 successful runs within 30 days
        for i in range(3):
            c.add(_record(f"r{i}", start_offset=i * 86400))
        m = c.compute(window_days=30)
        assert m.deploy_frequency == 3.0 / 30

    def test_lead_time(self) -> None:
        c = DORAMetricsCollector()
        c.add(_record("r1", duration=1000, succeeded=True))
        c.add(_record("r2", start_offset=100, duration=2000, succeeded=True))
        c.add(_record("r3", start_offset=200, duration=500, succeeded=False))
        m = c.compute()
        # only successful: avg(1000, 2000) = 1500
        assert m.lead_time_seconds == 1500.0

    def test_change_failure_rate(self) -> None:
        c = DORAMetricsCollector()
        c.add(_record("r1", succeeded=True))
        c.add(_record("r2", start_offset=100, succeeded=False))
        c.add(_record("r3", start_offset=200, succeeded=True))
        c.add(_record("r4", start_offset=300, succeeded=False))
        m = c.compute()
        assert m.change_failure_rate == 0.5

    def test_mttr_single_recovery(self) -> None:
        c = DORAMetricsCollector()
        # failure at t=0 (finishes at t=3600), recovery at t=7200 (finishes at t=10800)
        c.add(_record("r1", succeeded=False, start_offset=0, duration=3600))
        c.add(_record("r2", succeeded=True, start_offset=7200, duration=3600))
        m = c.compute()
        # recovery = 10800 - 3600 = 7200
        assert m.mean_time_to_restore_seconds == 7200.0

    def test_mttr_no_failures(self) -> None:
        c = DORAMetricsCollector()
        c.add(_record("r1", succeeded=True))
        m = c.compute()
        assert m.mean_time_to_restore_seconds == 0.0

    def test_mttr_multiple_projects(self) -> None:
        c = DORAMetricsCollector()
        # project A: fail then recover
        c.add(_record("a1", project_id="A", succeeded=False, start_offset=0, duration=100))
        c.add(_record("a2", project_id="A", succeeded=True, start_offset=200, duration=100))
        # project B: fail then recover
        c.add(_record("b1", project_id="B", succeeded=False, start_offset=0, duration=100))
        c.add(_record("b2", project_id="B", succeeded=True, start_offset=500, duration=100))
        m = c.compute()
        # A recovery: 300 - 100 = 200, B recovery: 600 - 100 = 500
        assert m.mean_time_to_restore_seconds == (200 + 500) / 2

    def test_window_filters_old_records(self) -> None:
        c = DORAMetricsCollector()
        # old record outside 7-day window
        c.add(_record("old", start_offset=0, duration=100, succeeded=True))
        # recent record within window
        c.add(_record("new", start_offset=86400 * 30, duration=100, succeeded=True))
        m = c.compute(window_days=7)
        # only 1 success in 7 days
        assert m.deploy_frequency == 1.0 / 7
