"""Metrics and statistics endpoints."""

from __future__ import annotations

from collections import defaultdict
import datetime as dt_mod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, Request

if TYPE_CHECKING:
    from lintel.projections.cost_metrics import CostMetricsProjection

router = APIRouter()


def get_agent_activity(request: Request) -> list[dict[str, Any]]:
    """Get agent activity log from app state."""
    if not hasattr(request.app.state, "agent_activity"):
        request.app.state.agent_activity = []
    return request.app.state.agent_activity  # type: ignore[no-any-return]


@router.get("/metrics/pii")
async def pii_metrics(request: Request) -> dict[str, Any]:
    """PII detection/anonymisation stats over time."""
    if not hasattr(request.app.state, "pii_stats"):
        request.app.state.pii_stats = {
            "total_scanned": 0,
            "total_detected": 0,
            "total_anonymised": 0,
            "total_blocked": 0,
            "total_reveals": 0,
        }
    return {
        "pii": request.app.state.pii_stats,
    }


@router.get("/metrics/agents")
async def agent_metrics(request: Request) -> dict[str, Any]:
    """Agent activity statistics."""
    activity = get_agent_activity(request)
    return {
        "total_steps": len(activity),
        "activity": activity[-100:],  # last 100 entries
    }


def _store_count(state: object, attr: str, items_attr: str = "") -> int:
    """Safely count items in an app-state store."""
    store = getattr(state, attr, None)
    if store is None:
        return 0
    if items_attr:
        container = getattr(store, items_attr, {})
    else:
        # Try common internal dict attribute names
        for name in (
            "_data",
            "_definitions",
            "_skills",
            "_models",
            "_runs",
            "_servers",
            "_items",
            "_teams",
            "_repos",
        ):
            container = getattr(store, name, None)
            if container is not None and isinstance(container, dict):
                return len(container)
        return 0
    return len(container) if isinstance(container, dict | list) else 0


@router.get("/metrics/overview")
async def overview_metrics(request: Request) -> dict[str, Any]:
    """Combined overview metrics for the dashboard."""
    state = request.app.state
    pii_stats: dict[str, int] = getattr(
        state,
        "pii_stats",
        {
            "total_scanned": 0,
            "total_detected": 0,
            "total_anonymised": 0,
            "total_blocked": 0,
            "total_reveals": 0,
        },
    )
    sandbox_registry: dict[str, Any] = getattr(state, "sandbox_registry", {})
    connections: dict[str, Any] = getattr(state, "connections", {})

    # Entity counts
    projects = _store_count(state, "project_store")
    pipelines = _store_count(state, "pipeline_store")
    work_items = _store_count(state, "work_item_store")
    models = _store_count(state, "model_store")
    agents = _store_count(state, "agent_definition_store")
    skills = _store_count(state, "skill_store")
    mcp_servers = _store_count(state, "mcp_server_store")
    repos = _store_count(state, "repository_store")

    # Event count from projection
    task_backlog = getattr(state, "task_backlog_projection", None)
    event_count = len(task_backlog.get_backlog()) if task_backlog else 0

    # Pipeline status breakdown
    pipeline_store = getattr(state, "pipeline_store", None)
    pipeline_by_status: dict[str, int] = {}
    if pipeline_store:
        runs: dict[str, Any] = getattr(pipeline_store, "_runs", {})
        for run in runs.values():
            status = getattr(run, "status", None)
            if status:
                key = status.value if hasattr(status, "value") else str(status)
                pipeline_by_status[key] = pipeline_by_status.get(key, 0) + 1

    # Work item status breakdown
    wi_store = getattr(state, "work_item_store", None)
    wi_by_status: dict[str, int] = {}
    if wi_store:
        items: dict[str, Any] = getattr(wi_store, "_data", getattr(wi_store, "_items", {}))
        if isinstance(items, dict):
            for item in items.values():
                if isinstance(item, dict):
                    raw_status = item.get("status", "unknown")
                else:
                    raw_status = getattr(item, "status", "unknown")
                if raw_status and hasattr(raw_status, "value"):
                    key = str(raw_status.value)
                else:
                    key = str(raw_status or "unknown")
                wi_by_status[key] = wi_by_status.get(key, 0) + 1

    # Recent events (last 10)
    recent_events: list[dict[str, Any]] = []
    if task_backlog:
        backlog = task_backlog.get_backlog()
        for ev in backlog[-10:]:
            if isinstance(ev, dict):
                recent_events.append(ev)
            else:
                recent_events.append({"event_type": str(ev)})

    # Agent activity count
    activity = get_agent_activity(request)

    return {
        "pii": pii_stats,
        "sandboxes": {"total": len(sandbox_registry)},
        "connections": {"total": len(connections)},
        "counts": {
            "projects": projects,
            "pipelines": pipelines,
            "work_items": work_items,
            "models": models,
            "agents": agents,
            "skills": skills,
            "mcp_servers": mcp_servers,
            "repos": repos,
            "events": event_count,
            "agent_steps": len(activity),
        },
        "pipelines_by_status": pipeline_by_status,
        "work_items_by_status": wi_by_status,
        "recent_events": recent_events,
    }


@router.get("/metrics/quality")
async def quality_metrics(
    request: Request,
    project_id: str = Query("", description="Filter by project ID (empty = all projects)"),
    days: int = Query(30, description="Rolling window in days (e.g. 30, 60, 90)"),
) -> dict[str, Any]:
    """Quality metrics: test coverage delta, defect density, rework ratio (MET-5)."""
    proj = getattr(request.app.state, "quality_metrics_projection", None)
    if proj is None:
        return {
            "coverage_deltas": [],
            "defect_density": {
                "bug_count": 0,
                "lines_changed": 0,
                "density": 0.0,
                "window_days": days,
            },
            "rework_ratio": {
                "rework_loc": 0,
                "total_loc": 0,
                "ratio": 0.0,
                "window_days": days,
            },
            "window_days": days,
        }
    result: dict[str, Any] = proj.get_quality_summary(project_id=project_id, days=days)
    return result


@router.get("/metrics/costs")
async def cost_metrics(
    request: Request,
    project_id: str = Query(..., description="Project ID (required)"),
    period: str = Query("daily", description="Aggregation period: daily or weekly"),
    run_id: str = Query("", description="Filter by pipeline run ID"),
    stage: str = Query("", description="Filter by pipeline stage"),
    agent_role: str = Query("", description="Filter by agent role"),
    start_date: str = Query("", description="Start date (YYYY-MM-DD)"),
    end_date: str = Query("", description="End date (YYYY-MM-DD)"),
) -> dict[str, Any]:
    """LLM cost metrics: total cost, token usage, breakdowns by model/stage/role."""
    proj: CostMetricsProjection | None = getattr(request.app.state, "cost_metrics_projection", None)
    if proj is None:
        return {
            "project_id": project_id,
            "total_cost_usd": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "call_count": 0,
            "breakdown_by_model": [],
            "breakdown_by_stage": [],
            "breakdown_by_role": [],
            "time_series": [],
        }

    # If filtering by run_id, return run-specific data
    if run_id:
        run_data = proj.get_costs_by_run(run_id)
        stage_data = proj.get_costs_by_stage(run_id)
        if stage and stage_data:
            stage_data = [s for s in stage_data if s.get("stage") == stage]
        return {
            "project_id": project_id,
            **{k: v for k, v in run_data.items() if k != "run_id"},
            "breakdown_by_model": [],
            "breakdown_by_stage": stage_data,
            "breakdown_by_role": [],
            "time_series": [],
        }

    # Project-level cost data
    result = proj.get_costs_by_project(
        project_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

    # Apply optional agent_role filter to breakdown
    if agent_role and result.get("breakdown_by_role"):
        result["breakdown_by_role"] = [
            r for r in result["breakdown_by_role"] if r.get("agent_role") == agent_role
        ]

    return result


@router.get("/metrics/pipelines")
async def pipeline_metrics(
    request: Request,
    project_id: str = Query("", description="Filter by project ID (empty = all)"),
    bucket: str = Query("daily", description="Time bucket: daily or weekly"),
) -> dict[str, Any]:
    """Pipeline success/failure metrics: totals, success rate, duration, runs over time."""
    pipeline_store = getattr(request.app.state, "pipeline_store", None)
    if pipeline_store is None:
        return _empty_pipeline_metrics()

    runs_dict: dict[str, Any] = getattr(pipeline_store, "_runs", {})
    runs = list(runs_dict.values())

    if project_id:
        runs = [r for r in runs if _run_attr(r, "project_id", "") == project_id]

    total = len(runs)
    succeeded = 0
    failed = 0
    cancelled = 0
    running = 0
    total_duration_ms = 0
    duration_count = 0
    failure_reasons: dict[str, int] = defaultdict(int)
    time_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"succeeded": 0, "failed": 0, "cancelled": 0, "total": 0},
    )

    for run in runs:
        status = _run_attr(run, "status", "pending")
        status_str = status.value if hasattr(status, "value") else str(status)

        if status_str == "succeeded":
            succeeded += 1
        elif status_str == "failed":
            failed += 1
        elif status_str == "cancelled":
            cancelled += 1
        elif status_str == "running":
            running += 1

        # Aggregate durations from stages
        stages = _run_attr(run, "stages", ())
        run_duration = 0
        for stage in stages:
            d = _run_attr(stage, "duration_ms", 0)
            if isinstance(d, int) and d > 0:
                run_duration += d
        if run_duration > 0:
            total_duration_ms += run_duration
            duration_count += 1

        # Failure reasons from failed stages
        if status_str == "failed":
            for stage in stages:
                s_status = _run_attr(stage, "status", "pending")
                s_str = s_status.value if hasattr(s_status, "value") else str(s_status)
                if s_str == "failed":
                    error = _run_attr(stage, "error", "")
                    reason = str(error)[:80] if error else "unknown"
                    failure_reasons[reason] += 1

        # Time bucketing
        created_at = _run_attr(run, "created_at", "")
        bucket_key = _to_bucket_key(str(created_at), bucket)
        if bucket_key and status_str in time_buckets[bucket_key]:
            time_buckets[bucket_key][status_str] += 1
            time_buckets[bucket_key]["total"] += 1

    success_rate = (succeeded / total * 100) if total > 0 else 0.0
    avg_duration_ms = (total_duration_ms // duration_count) if duration_count > 0 else 0

    # Sort time series
    sorted_buckets = sorted(time_buckets.items())
    runs_over_time = [{"date": k, **v} for k, v in sorted_buckets]

    # Sort failure reasons by count descending
    failure_breakdown = [
        {"reason": r, "count": c} for r, c in sorted(failure_reasons.items(), key=lambda x: -x[1])
    ]

    return {
        "total_runs": total,
        "succeeded": succeeded,
        "failed": failed,
        "cancelled": cancelled,
        "running": running,
        "success_rate": round(success_rate, 1),
        "avg_duration_ms": avg_duration_ms,
        "runs_over_time": runs_over_time,
        "failure_reasons": failure_breakdown,
    }


def _run_attr(obj: object, attr: str, default: object = None) -> object:
    """Get attribute from dataclass or dict."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _to_bucket_key(created_at: str, bucket: str) -> str:
    """Convert ISO timestamp to a date bucket key."""
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""
    if bucket == "weekly":
        # ISO week start (Monday)
        monday = dt.date() - dt_mod.timedelta(days=dt.weekday())
        return monday.isoformat()
    return dt.date().isoformat()


def _empty_pipeline_metrics() -> dict[str, Any]:
    """Return empty pipeline metrics response."""
    return {
        "total_runs": 0,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
        "running": 0,
        "success_rate": 0.0,
        "avg_duration_ms": 0,
        "runs_over_time": [],
        "failure_reasons": [],
    }
