"""Automation CRUD endpoints."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request

from lintel.api.container import AppContainer
from lintel.api.schemas.automations import CreateAutomationRequest, UpdateAutomationRequest
from lintel.contracts.events import (
    AutomationCreated,
    AutomationDisabled,
    AutomationEnabled,
    AutomationFired,
    AutomationRemoved,
    AutomationUpdated,
)
from lintel.contracts.types import AutomationDefinition, PipelineRun
from lintel.domain.event_dispatcher import dispatch_event

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class InMemoryAutomationStore:
    """Simple in-memory store for automations."""

    def __init__(self) -> None:
        self._automations: dict[str, AutomationDefinition] = {}

    async def add(self, automation: AutomationDefinition) -> None:
        self._automations[automation.automation_id] = automation

    async def get(self, automation_id: str) -> AutomationDefinition | None:
        return self._automations.get(automation_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[AutomationDefinition]:
        items = list(self._automations.values())
        if project_id is not None:
            items = [a for a in items if a.project_id == project_id]
        return items

    async def update(self, automation: AutomationDefinition) -> None:
        if automation.automation_id not in self._automations:
            msg = f"Automation {automation.automation_id} not found"
            raise KeyError(msg)
        self._automations[automation.automation_id] = automation

    async def remove(self, automation_id: str) -> None:
        if automation_id not in self._automations:
            msg = f"Automation {automation_id} not found"
            raise KeyError(msg)
        del self._automations[automation_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/automations", status_code=201)
@inject
async def create_automation(
    body: CreateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.automation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Automation already exists")
    now = datetime.now(UTC).isoformat()
    automation = AutomationDefinition(
        automation_id=body.automation_id,
        name=body.name,
        project_id=body.project_id,
        workflow_definition_id=body.workflow_definition_id,
        trigger_type=body.trigger_type,
        trigger_config=body.trigger_config,
        input_parameters=body.input_parameters,
        concurrency_policy=body.concurrency_policy,
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )
    await store.add(automation)
    await dispatch_event(
        request,
        AutomationCreated(payload={"resource_id": automation.automation_id}),
        stream_id=f"automation:{automation.automation_id}",
    )
    return asdict(automation)


@router.get("/automations")
@inject
async def list_automations(
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    automations = await store.list_all(project_id=project_id)
    return [asdict(a) for a in automations]


@router.get("/automations/{automation_id}")
@inject
async def get_automation(
    automation_id: str,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return asdict(automation)


@router.patch("/automations/{automation_id}")
@inject
async def update_automation(
    automation_id: str,
    body: UpdateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    updates = body.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now(UTC).isoformat()
    updated = AutomationDefinition(**{**asdict(automation), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        AutomationUpdated(payload={"resource_id": automation_id}),
        stream_id=f"automation:{automation_id}",
    )
    # Emit enabled/disabled events when toggled
    if "enabled" in updates and updates["enabled"] != automation.enabled:
        evt_cls = AutomationEnabled if updates["enabled"] else AutomationDisabled
        await dispatch_event(
            request,
            evt_cls(payload={"resource_id": automation_id}),
            stream_id=f"automation:{automation_id}",
        )
    return asdict(updated)


@router.delete("/automations/{automation_id}", status_code=204)
@inject
async def delete_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> None:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    await store.remove(automation_id)
    await dispatch_event(
        request,
        AutomationRemoved(payload={"resource_id": automation_id}),
        stream_id=f"automation:{automation_id}",
    )


@router.post("/automations/{automation_id}/trigger")
@inject
async def trigger_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    pipeline_store: Any = Depends(Provide[AppContainer.pipeline_store]),  # noqa: ANN401, B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation is disabled")

    run_id = str(uuid4())
    pipeline_run = PipelineRun(
        run_id=run_id,
        project_id=automation.project_id,
        work_item_id="",
        workflow_definition_id=automation.workflow_definition_id,
        trigger_type=f"automation:{automation_id}",
    )
    await pipeline_store.add(pipeline_run)
    await dispatch_event(
        request,
        AutomationFired(
            payload={
                "resource_id": automation_id,
                "pipeline_run_id": run_id,
                "trigger_type": "manual",
            },
        ),
        stream_id=f"automation:{automation_id}",
    )
    return {"automation_id": automation_id, "pipeline_run_id": run_id}


@router.get("/automations/{automation_id}/runs")
@inject
async def list_automation_runs(
    automation_id: str,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    pipeline_store: Any = Depends(Provide[AppContainer.pipeline_store]),  # noqa: ANN401, B008
) -> list[dict[str, Any]]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    all_runs = await pipeline_store.list_all()
    prefix = f"automation:{automation_id}"
    matching = [r for r in all_runs if _get_trigger_type(r) == prefix]
    return [asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in matching]


def _get_trigger_type(run: Any) -> str:  # noqa: ANN401
    """Extract trigger_type from either a dataclass or dict."""
    if isinstance(run, dict):
        return str(run.get("trigger_type", ""))
    return str(getattr(run, "trigger_type", ""))
