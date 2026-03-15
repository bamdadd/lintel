"""Compliance configuration and overview endpoints."""

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.domain.events import ProjectUpdated

if TYPE_CHECKING:
    from lintel.compliance_api.store import ComplianceStore

router = APIRouter()

_DEFAULT_CONFIG: dict[str, bool] = {
    "enabled": False,
    "regulations_enabled": True,
    "policies_enabled": True,
    "procedures_enabled": True,
    "practices_enabled": True,
    "strategies_enabled": True,
    "kpis_enabled": True,
    "experiments_enabled": True,
    "metrics_enabled": True,
    "knowledge_base_enabled": True,
}


class UpdateComplianceConfigRequest(BaseModel):
    enabled: bool | None = None
    regulations_enabled: bool | None = None
    policies_enabled: bool | None = None
    procedures_enabled: bool | None = None
    practices_enabled: bool | None = None
    strategies_enabled: bool | None = None
    kpis_enabled: bool | None = None
    experiments_enabled: bool | None = None
    metrics_enabled: bool | None = None
    knowledge_base_enabled: bool | None = None


@router.get("/compliance/config/{project_id}")
async def get_compliance_config(
    project_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get compliance configuration for a project."""
    store = request.app.state.project_store
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    config = project.get("compliance_config", dict(_DEFAULT_CONFIG))
    return {"project_id": project_id, **config}


@router.patch("/compliance/config/{project_id}")
async def update_compliance_config(
    project_id: str,
    body: UpdateComplianceConfigRequest,
    request: Request,
) -> dict[str, Any]:
    """Enable/disable compliance features for a project."""
    store = request.app.state.project_store
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    current_config = project.get("compliance_config", dict(_DEFAULT_CONFIG))
    updates = body.model_dump(exclude_none=True)
    merged_config = {**current_config, **updates}
    project["compliance_config"] = merged_config
    await store.update(project_id, project)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={
                "resource_id": project_id,
                "fields": ["compliance_config"],
                "compliance_config": merged_config,
            }
        ),
        stream_id=f"project:{project_id}",
    )
    return {"project_id": project_id, **merged_config}


@router.get("/compliance/overview/{project_id}")
async def compliance_overview(
    project_id: str,
    request: Request,
) -> dict[str, Any]:
    """Aggregated compliance governance overview for a project."""
    reg_store: ComplianceStore = request.app.state.regulation_store
    pol_store: ComplianceStore = request.app.state.compliance_policy_store
    proc_store: ComplianceStore = request.app.state.procedure_store
    prac_store: ComplianceStore = request.app.state.practice_store
    strat_store: ComplianceStore = request.app.state.strategy_store
    kpi_store: ComplianceStore = request.app.state.kpi_store
    exp_store: ComplianceStore = request.app.state.experiment_store
    met_store: ComplianceStore = request.app.state.compliance_metric_store
    kb_store: ComplianceStore = request.app.state.knowledge_entry_store
    adr_store: ComplianceStore = request.app.state.architecture_decision_store

    regulations = await reg_store.list_by_project(project_id)
    policies = await pol_store.list_by_project(project_id)
    procedures = await proc_store.list_by_project(project_id)
    practices = await prac_store.list_by_project(project_id)
    strategies = await strat_store.list_by_project(project_id)
    kpis = await kpi_store.list_by_project(project_id)
    experiments = await exp_store.list_by_project(project_id)
    metrics = await met_store.list_by_project(project_id)
    knowledge = await kb_store.list_by_project(project_id)
    adrs = await adr_store.list_by_project(project_id)

    # Compute risk distribution
    all_items = regulations + policies + procedures + practices
    risk_counts: dict[str, int] = {}
    for item in all_items:
        rl = item.get("risk_level", "medium")
        risk_counts[rl] = risk_counts.get(rl, 0) + 1

    # Compute status distribution
    status_counts: dict[str, int] = {}
    for item in all_items:
        st = item.get("status", "draft")
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "project_id": project_id,
        "counts": {
            "regulations": len(regulations),
            "policies": len(policies),
            "procedures": len(procedures),
            "practices": len(practices),
            "strategies": len(strategies),
            "kpis": len(kpis),
            "experiments": len(experiments),
            "metrics": len(metrics),
            "knowledge_entries": len(knowledge),
            "architecture_decisions": len(adrs),
        },
        "risk_distribution": risk_counts,
        "status_distribution": status_counts,
        "cascade": {
            "regulations": regulations,
            "policies": policies,
            "procedures": procedures,
            "practices": practices,
        },
        "strategies": strategies,
        "kpis": kpis,
        "architecture_decisions": adrs,
    }
