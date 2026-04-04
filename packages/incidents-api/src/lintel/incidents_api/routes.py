"""Incident hotfix API endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import WorkItemCreated
from lintel.incidents_api.handler import IncidentHotfixHandler

if TYPE_CHECKING:
    from lintel.incidents_api.store import InMemoryIncidentStore

router = APIRouter()

incident_store_provider: StoreProvider[InMemoryIncidentStore] = StoreProvider()

_handler = IncidentHotfixHandler()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateIncidentFromAlertRequest(BaseModel):
    """Parse a Slack alert and create an incident + dispatch hotfix."""

    alert_text: str = Field(..., min_length=1, description="Raw Slack alert text")
    source: str = Field(default="slack", description="Alert source (e.g. slack, pagerduty)")
    project_id: str = Field(..., min_length=1, description="Project to create hotfix in")
    repo_url: str = Field(default="", description="Repository URL for the hotfix branch")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/incidents/from-alert", status_code=201)
async def create_incident_from_alert(
    body: CreateIncidentFromAlertRequest,
    request: Request,
    store: InMemoryIncidentStore = Depends(incident_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Parse a Slack alert, create an incident, and dispatch a bug_fix workflow."""
    incident, command = _handler.from_alert_text(
        body.alert_text,
        source=body.source,
        project_id=body.project_id,
        repo_url=body.repo_url,
    )

    # Persist incident
    await store.add(incident.incident_id, asdict(incident))

    # Emit domain event
    await dispatch_event(
        request,
        WorkItemCreated(payload={"resource_id": incident.incident_id}),
        stream_id=f"incident:{incident.incident_id}",
    )

    # Dispatch the hotfix workflow
    executor = getattr(request.app.state, "workflow_executor", None)
    run_id = ""
    if executor is not None:
        run_id = await executor.execute(command)

    return {
        "incident_id": incident.incident_id,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "title": incident.title,
        "hotfix_branch": command.repo_branch,
        "workflow_run_id": run_id,
    }


@router.get("/incidents")
async def list_incidents(
    store: InMemoryIncidentStore = Depends(incident_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all incidents, optionally filtered by project."""
    return await store.list_all(project_id=project_id)


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    store: InMemoryIncidentStore = Depends(incident_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a single incident by ID."""
    incident = await store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
