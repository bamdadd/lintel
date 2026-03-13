"""Metrics and statistics endpoints."""

from typing import Any

from fastapi import APIRouter, Query, Request

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
    return proj.get_quality_summary(project_id=project_id, days=days)
