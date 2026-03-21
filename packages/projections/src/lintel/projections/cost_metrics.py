"""Cost metrics projection — aggregates LLM call cost data from ModelCallCompleted events.

Maintains in-memory read models for:
* per-run totals
* per-run+stage totals
* per-project daily totals
* per-agent-role totals
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


@dataclass
class CostBucket:
    """Aggregated cost + token counters."""

    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    call_count: int = 0

    def add(
        self,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        self.total_cost_usd += cost_usd
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost_usd, 8),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "call_count": self.call_count,
        }


@dataclass
class ModelCallRecord:
    """Single model call entry for the raw log."""

    event_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    agent_role: str
    run_id: str
    stage: str
    project_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CostMetricsProjection:
    """Builds aggregated cost read-models from ``ModelCallCompleted`` events."""

    HANDLED_TYPES: frozenset[str] = frozenset({"ModelCallCompleted"})

    def __init__(self) -> None:
        self._raw_events: list[ModelCallRecord] = []
        # event_id dedup set
        self._seen_ids: set[str] = set()
        # Aggregation buckets
        self._by_run: dict[str, CostBucket] = {}
        self._by_stage: dict[tuple[str, str], CostBucket] = {}
        self._by_project_daily: dict[tuple[str, str], CostBucket] = {}
        self._by_agent_role: dict[tuple[str, str], CostBucket] = {}
        # Per-model breakdown
        self._by_model: dict[str, CostBucket] = {}

    # -- Projection protocol ------------------------------------------------

    @property
    def name(self) -> str:
        return "cost_metrics"

    def get_state(self) -> dict[str, Any]:
        return {
            "raw_events": [
                {
                    "event_id": r.event_id,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd,
                    "duration_ms": r.duration_ms,
                    "agent_role": r.agent_role,
                    "run_id": r.run_id,
                    "stage": r.stage,
                    "project_id": r.project_id,
                    "occurred_at": r.occurred_at.isoformat(),
                }
                for r in self._raw_events
            ],
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._raw_events.clear()
        self._seen_ids.clear()
        self._by_run.clear()
        self._by_stage.clear()
        self._by_project_daily.clear()
        self._by_agent_role.clear()
        self._by_model.clear()
        for r in state.get("raw_events", []):
            occ = r.get("occurred_at", "")
            dt = datetime.fromisoformat(occ) if isinstance(occ, str) and occ else datetime.now(UTC)
            rec = ModelCallRecord(
                event_id=r["event_id"],
                model=r["model"],
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                cost_usd=r["cost_usd"],
                duration_ms=r["duration_ms"],
                agent_role=r["agent_role"],
                run_id=r["run_id"],
                stage=r["stage"],
                project_id=r["project_id"],
                occurred_at=dt,
            )
            self._ingest(rec)

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        eid = str(event.event_id)
        if eid in self._seen_ids:
            return  # idempotent
        payload = event.payload
        rec = ModelCallRecord(
            event_id=eid,
            model=payload.get("model", ""),
            input_tokens=int(payload.get("input_tokens", 0)),
            output_tokens=int(payload.get("output_tokens", 0)),
            cost_usd=float(payload.get("cost_usd", 0.0)),
            duration_ms=int(payload.get("duration_ms", 0)),
            agent_role=payload.get("agent_role", ""),
            run_id=payload.get("run_id", ""),
            stage=payload.get("stage", ""),
            project_id=payload.get("project_id", ""),
            occurred_at=event.occurred_at,
        )
        self._ingest(rec)

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._raw_events.clear()
        self._seen_ids.clear()
        self._by_run.clear()
        self._by_stage.clear()
        self._by_project_daily.clear()
        self._by_agent_role.clear()
        self._by_model.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    # -- Internal -----------------------------------------------------------

    def _ingest(self, rec: ModelCallRecord) -> None:
        self._seen_ids.add(rec.event_id)
        self._raw_events.append(rec)

        cost = rec.cost_usd
        inp = rec.input_tokens
        out = rec.output_tokens

        # Per run
        if rec.run_id:
            bucket = self._by_run.setdefault(rec.run_id, CostBucket())
            bucket.add(cost, inp, out)

        # Per run+stage
        if rec.run_id and rec.stage:
            key = (rec.run_id, rec.stage)
            bucket = self._by_stage.setdefault(key, CostBucket())
            bucket.add(cost, inp, out)

        # Per project+day
        if rec.project_id:
            day_str = rec.occurred_at.date().isoformat()
            key_pd = (rec.project_id, day_str)
            bucket = self._by_project_daily.setdefault(key_pd, CostBucket())
            bucket.add(cost, inp, out)

        # Per agent_role (scoped to project)
        if rec.agent_role:
            key_ar = (rec.agent_role, rec.project_id or "")
            bucket = self._by_agent_role.setdefault(key_ar, CostBucket())
            bucket.add(cost, inp, out)

        # Per model
        if rec.model:
            bucket = self._by_model.setdefault(rec.model, CostBucket())
            bucket.add(cost, inp, out)

    # -- Query helpers ------------------------------------------------------

    def get_costs_by_run(self, run_id: str) -> dict[str, Any]:
        """Return aggregated cost metrics for a single pipeline run."""
        bucket = self._by_run.get(run_id)
        if bucket is None:
            return {"run_id": run_id, **CostBucket().to_dict()}
        return {"run_id": run_id, **bucket.to_dict()}

    def get_costs_by_stage(self, run_id: str) -> list[dict[str, Any]]:
        """Return per-stage breakdown for a run."""
        results: list[dict[str, Any]] = []
        for (rid, stage), bucket in self._by_stage.items():
            if rid == run_id:
                results.append({"run_id": rid, "stage": stage, **bucket.to_dict()})
        return results

    def get_costs_by_project(
        self,
        project_id: str,
        *,
        period: str = "daily",
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        """Return cost metrics for a project with time series."""
        total = CostBucket()
        time_series: list[dict[str, Any]] = []
        model_breakdown: dict[str, CostBucket] = {}
        role_breakdown: dict[str, CostBucket] = {}
        stage_breakdown: dict[str, CostBucket] = {}

        for rec in self._raw_events:
            if rec.project_id != project_id:
                continue
            if start_date and rec.occurred_at.date().isoformat() < start_date:
                continue
            if end_date and rec.occurred_at.date().isoformat() > end_date:
                continue

            total.add(rec.cost_usd, rec.input_tokens, rec.output_tokens)

            if rec.model:
                b = model_breakdown.setdefault(rec.model, CostBucket())
                b.add(rec.cost_usd, rec.input_tokens, rec.output_tokens)
            if rec.agent_role:
                b = role_breakdown.setdefault(rec.agent_role, CostBucket())
                b.add(rec.cost_usd, rec.input_tokens, rec.output_tokens)
            if rec.stage:
                b = stage_breakdown.setdefault(rec.stage, CostBucket())
                b.add(rec.cost_usd, rec.input_tokens, rec.output_tokens)

        # Build time series from project daily buckets
        for (pid, day_str), bucket in sorted(self._by_project_daily.items()):
            if pid != project_id:
                continue
            if start_date and day_str < start_date:
                continue
            if end_date and day_str > end_date:
                continue
            time_series.append({"date": day_str, **bucket.to_dict()})

        # Weekly aggregation if requested
        if period == "weekly" and time_series:
            time_series = self._aggregate_weekly(time_series)

        return {
            "project_id": project_id,
            **total.to_dict(),
            "breakdown_by_model": [
                {"model": m, **b.to_dict()} for m, b in sorted(model_breakdown.items())
            ],
            "breakdown_by_stage": [
                {"stage": s, **b.to_dict()} for s, b in sorted(stage_breakdown.items())
            ],
            "breakdown_by_role": [
                {"agent_role": r, **b.to_dict()} for r, b in sorted(role_breakdown.items())
            ],
            "time_series": time_series,
        }

    def get_costs_by_agent_role(
        self,
        *,
        project_id: str = "",
    ) -> list[dict[str, Any]]:
        """Return per-agent-role cost breakdown."""
        results: list[dict[str, Any]] = []
        for (role, pid), bucket in sorted(self._by_agent_role.items()):
            if project_id and pid != project_id:
                continue
            results.append({"agent_role": role, "project_id": pid, **bucket.to_dict()})
        return results

    def get_all_raw_events(
        self,
        *,
        project_id: str = "",
        run_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return raw model call records (most recent first)."""
        filtered = self._raw_events
        if project_id:
            filtered = [r for r in filtered if r.project_id == project_id]
        if run_id:
            filtered = [r for r in filtered if r.run_id == run_id]
        results: list[dict[str, Any]] = []
        for r in reversed(filtered[-limit:]):
            results.append(
                {
                    "event_id": r.event_id,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd,
                    "duration_ms": r.duration_ms,
                    "agent_role": r.agent_role,
                    "run_id": r.run_id,
                    "stage": r.stage,
                    "project_id": r.project_id,
                    "occurred_at": r.occurred_at.isoformat(),
                }
            )
        return results

    @staticmethod
    def _aggregate_weekly(daily_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggregate daily time series into ISO week buckets."""
        from datetime import date as _date

        weeks: dict[str, CostBucket] = {}
        for entry in daily_series:
            d = _date.fromisoformat(entry["date"])
            # ISO week start (Monday)
            week_start = d - timedelta(days=d.weekday())
            ws = week_start.isoformat()
            b = weeks.setdefault(ws, CostBucket())
            b.add(
                entry.get("total_cost_usd", 0.0),
                entry.get("total_input_tokens", 0),
                entry.get("total_output_tokens", 0),
            )
        return [{"date": ws, **b.to_dict()} for ws, b in sorted(weeks.items())]
