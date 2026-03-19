"""Automation CRUD endpoints."""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.automations_api.schemas import CreateAutomationRequest, UpdateAutomationRequest
from lintel.contracts.types import ThreadRef
from lintel.domain.events import (
    AutomationCreated,
    AutomationDisabled,
    AutomationEnabled,
    AutomationFired,
    AutomationRemoved,
    AutomationUpdated,
)
from lintel.domain.types import AutomationDefinition
from lintel.workflows.commands import StartWorkflow
from lintel.workflows.types import PipelineRun

logger = logging.getLogger(__name__)

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


# Store provider
automation_store_provider: StoreProvider[InMemoryAutomationStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/automations", status_code=201)
async def create_automation(
    body: CreateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
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
async def list_automations(
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    automations = await store.list_all(project_id=project_id)
    return [asdict(a) for a in automations]


@router.get("/automations/{automation_id}")
async def get_automation(
    automation_id: str,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return asdict(automation)


@router.patch("/automations/{automation_id}")
async def update_automation(
    automation_id: str,
    body: UpdateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
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
async def delete_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
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
async def trigger_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation is disabled")

    pipeline_store = getattr(request.app.state, "pipeline_store", None)
    run_id = str(uuid4())
    pipeline_run = PipelineRun(
        run_id=run_id,
        project_id=automation.project_id,
        work_item_id="",
        workflow_definition_id=automation.workflow_definition_id,
        trigger_type=f"automation:{automation_id}",
    )
    if pipeline_store:
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

    # Dispatch StartWorkflow to actually execute the pipeline
    dispatcher = getattr(request.app.state, "command_dispatcher", None)
    if dispatcher:
        thread_ref = ThreadRef(
            workspace_id="lintel",
            channel_id=f"automation:{automation_id}",
            thread_ts=run_id,
        )
        command = StartWorkflow(
            thread_ref=thread_ref,
            workflow_type=automation.workflow_definition_id or "feature_to_pr",
            project_id=automation.project_id,
            run_id=run_id,
            trigger_context=f"automation:{automation_id}",
        )
        task = asyncio.create_task(dispatcher.dispatch(command))
        bg: set[asyncio.Task[None]] = getattr(request.app.state, "_background_tasks", set())
        request.app.state._background_tasks = bg
        bg.add(task)
        task.add_done_callback(bg.discard)
        logger.info(
            "automation_workflow_dispatched",
            extra={"automation_id": automation_id, "run_id": run_id},
        )

    return {"automation_id": automation_id, "pipeline_run_id": run_id}


@router.get("/automations/{automation_id}/runs")
async def list_automation_runs(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(automation_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    pipeline_store = request.app.state.pipeline_store
    all_runs = await pipeline_store.list_all()
    prefix = f"automation:{automation_id}"
    matching = [r for r in all_runs if _get_trigger_type(r) == prefix]
    return [asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in matching]


def _get_trigger_type(run: Any) -> str:  # noqa: ANN401
    """Extract trigger_type from either a dataclass or dict."""
    if isinstance(run, dict):
        return str(run.get("trigger_type", ""))
    return str(getattr(run, "trigger_type", ""))
