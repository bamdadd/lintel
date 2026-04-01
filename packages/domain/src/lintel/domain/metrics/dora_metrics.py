"""DORA metrics — Deployment Frequency, Lead Time, Change Failure Rate, MTTR.

See docs/requirements/metrics.md MET-2 for specification.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum


class DORALevel(StrEnum):
    """DORA performance classification."""

    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineRunRecord:
    """Lightweight record derived from pipeline run events.

    Each record captures the outcome of a single pipeline run that is
    relevant for DORA metric computation.
    """

    run_id: str
    project_id: str
    started_at: float  # epoch seconds
    finished_at: float  # epoch seconds
    succeeded: bool


@dataclass(frozen=True)
class DORAMetrics:
    """Computed DORA metrics for a project over a time window.

    All four key metrics from the *Accelerate* / DORA framework:
    - deploy_frequency: successful deployments per day
    - lead_time_seconds: average seconds from run start to successful finish
    - change_failure_rate: ratio of failed runs to total runs (0.0 - 1.0)
    - mean_time_to_restore_seconds: average seconds between a failure and the
      next success for the same project
    """

    deploy_frequency: float
    lead_time_seconds: float
    change_failure_rate: float
    mean_time_to_restore_seconds: float

    # Derived classifications

    @property
    def deploy_frequency_level(self) -> DORALevel:
        return classify_deploy_frequency(self.deploy_frequency)

    @property
    def lead_time_level(self) -> DORALevel:
        return classify_lead_time(self.lead_time_seconds)

    @property
    def change_failure_rate_level(self) -> DORALevel:
        return classify_change_failure_rate(self.change_failure_rate)

    @property
    def mttr_level(self) -> DORALevel:
        return classify_mttr(self.mean_time_to_restore_seconds)


# ---------------------------------------------------------------------------
# Classification helpers (thresholds from MET-2 spec)
# ---------------------------------------------------------------------------

_SECONDS_PER_HOUR = 3600.0
_SECONDS_PER_DAY = 86400.0
_SECONDS_PER_WEEK = 604800.0
_SECONDS_PER_MONTH = 2592000.0  # 30 days


def classify_deploy_frequency(deploys_per_day: float) -> DORALevel:
    """Classify deployment frequency per DORA thresholds."""
    if deploys_per_day >= 1.0:
        return DORALevel.ELITE
    if deploys_per_day >= 1.0 / 7:
        return DORALevel.HIGH
    if deploys_per_day >= 1.0 / 30:
        return DORALevel.MEDIUM
    return DORALevel.LOW


def classify_lead_time(seconds: float) -> DORALevel:
    """Classify lead time for changes per DORA thresholds."""
    if seconds <= _SECONDS_PER_HOUR:
        return DORALevel.ELITE
    if seconds <= _SECONDS_PER_WEEK:
        return DORALevel.HIGH
    if seconds <= _SECONDS_PER_MONTH:
        return DORALevel.MEDIUM
    return DORALevel.LOW


def classify_change_failure_rate(rate: float) -> DORALevel:
    """Classify change failure rate per DORA thresholds."""
    if rate <= 0.05:
        return DORALevel.ELITE
    if rate <= 0.10:
        return DORALevel.HIGH
    if rate <= 0.15:
        return DORALevel.MEDIUM
    return DORALevel.LOW


def classify_mttr(seconds: float) -> DORALevel:
    """Classify mean time to recovery per DORA thresholds."""
    if seconds <= _SECONDS_PER_HOUR:
        return DORALevel.ELITE
    if seconds <= _SECONDS_PER_DAY:
        return DORALevel.HIGH
    if seconds <= _SECONDS_PER_WEEK:
        return DORALevel.MEDIUM
    return DORALevel.LOW


# ---------------------------------------------------------------------------
# Collector — computes DORAMetrics from a sequence of PipelineRunRecords
# ---------------------------------------------------------------------------

_ZERO_METRICS = DORAMetrics(
    deploy_frequency=0.0,
    lead_time_seconds=0.0,
    change_failure_rate=0.0,
    mean_time_to_restore_seconds=0.0,
)


@dataclass
class DORAMetricsCollector:
    """Computes DORA metrics from pipeline run records.

    Usage::

        collector = DORAMetricsCollector()
        collector.add(record)
        metrics = collector.compute(window_days=30)
    """

    _records: list[PipelineRunRecord] = field(default_factory=list)

    # -- mutation ----------------------------------------------------------

    def add(self, record: PipelineRunRecord) -> None:
        """Append a pipeline run record."""
        self._records.append(record)

    # -- query -------------------------------------------------------------

    def compute(self, window_days: int = 30) -> DORAMetrics:
        """Compute DORA metrics over *window_days*.

        If there are no records the result is all-zeros.
        """
        if not self._records:
            return _ZERO_METRICS

        window_seconds = window_days * _SECONDS_PER_DAY
        cutoff = max(r.finished_at for r in self._records) - window_seconds
        window = [r for r in self._records if r.finished_at >= cutoff]

        if not window:
            return _ZERO_METRICS

        return DORAMetrics(
            deploy_frequency=_deploy_frequency(window, window_days),
            lead_time_seconds=_lead_time(window),
            change_failure_rate=_change_failure_rate(window),
            mean_time_to_restore_seconds=_mttr(window),
        )


# ---------------------------------------------------------------------------
# Internal calculation helpers
# ---------------------------------------------------------------------------


def _deploy_frequency(records: list[PipelineRunRecord], window_days: int) -> float:
    """Successful deployments per day."""
    successes = sum(1 for r in records if r.succeeded)
    return successes / max(window_days, 1)


def _lead_time(records: list[PipelineRunRecord]) -> float:
    """Average lead time (start -> finish) for successful runs, in seconds."""
    durations = [r.finished_at - r.started_at for r in records if r.succeeded]
    if not durations:
        return 0.0
    return sum(durations) / len(durations)


def _change_failure_rate(records: list[PipelineRunRecord]) -> float:
    """Ratio of failed runs to total runs."""
    total = len(records)
    if total == 0:
        return 0.0
    failures = sum(1 for r in records if not r.succeeded)
    return failures / total


def _mttr(records: list[PipelineRunRecord]) -> float:
    """Mean time to restore: average gap between a failure and the next success.

    Records are grouped by project_id and sorted chronologically.  For each
    failure we find the next success in the same project; the delta is one
    recovery episode.
    """
    by_project: dict[str, list[PipelineRunRecord]] = defaultdict(list)
    for r in records:
        by_project[r.project_id].append(r)

    recovery_times: list[float] = []
    for project_records in by_project.values():
        sorted_runs = sorted(project_records, key=lambda r: r.finished_at)
        pending_failure: PipelineRunRecord | None = None
        for run in sorted_runs:
            if not run.succeeded:
                if pending_failure is None:
                    pending_failure = run
            elif pending_failure is not None:
                recovery_times.append(run.finished_at - pending_failure.finished_at)
                pending_failure = None

    if not recovery_times:
        return 0.0
    return sum(recovery_times) / len(recovery_times)
