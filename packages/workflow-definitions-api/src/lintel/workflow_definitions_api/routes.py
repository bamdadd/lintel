"""Workflow template and graph definition CRUD endpoints."""

import dataclasses
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.workflow_definitions_api.store import InMemoryWorkflowDefinitionStore
from lintel.workflows.events import (
    WorkflowDefinitionCreated,
    WorkflowDefinitionRemoved,
    WorkflowDefinitionUpdated,
)

router = APIRouter()

workflow_definition_store_provider: StoreProvider[InMemoryWorkflowDefinitionStore] = StoreProvider()


def _wf_to_dict(wf: object) -> dict[str, Any]:
    """Convert a WorkflowDefinitionRecord to the API dict format."""
    data = dataclasses.asdict(wf)  # type: ignore[call-overload]
    now = datetime.now(UTC).isoformat()
    # Rebuild into the nested graph format the UI expects
    return {
        "definition_id": data["definition_id"],
        "name": data["name"],
        "description": data["description"],
        "is_template": data["is_template"],
        "is_builtin": data.get("is_builtin", False),
        "tags": list(data.get("tags", [])),
        "graph": {
            "nodes": list(data.get("graph_nodes", [])),
            "edges": [list(e) for e in data.get("graph_edges", [])],
            "conditional_edges": [dict(e) for e in data.get("conditional_edges", [])],
            "entry_point": data.get("entry_point", ""),
            "interrupt_before": list(data.get("interrupt_before", [])),
            "node_metadata": {
                m["node"]: {k: v for k, v in m.items() if k != "node"}
                for m in data.get("node_metadata", [])
            },
        },
        "stage_names": list(data.get("stage_names", [])),
        "step_configs": [dict(sc) for sc in data.get("step_configs", [])],
        "enabled": data.get("enabled", True),
        "created_at": now,
        "updated_at": now,
    }


_seeded_stores: set[int] = set()


async def _ensure_seeded(store: InMemoryWorkflowDefinitionStore) -> None:
    """Seed builtin workflow definitions, adding any missing builtins."""
    store_id = id(store)
    if store_id in _seeded_stores:
        return
    from lintel.domain.seed import DEFAULT_WORKFLOW_DEFINITIONS

    existing = await store.list_all()
    existing_ids = {e["definition_id"] for e in existing} if existing else set()

    for wf in DEFAULT_WORKFLOW_DEFINITIONS:
        if wf.definition_id not in existing_ids:
            d = _wf_to_dict(wf)
            d.setdefault("enabled", True)
            await store.put(wf.definition_id, d)
    _seeded_stores.add(store_id)


class CreateWorkflowDefRequest(BaseModel):
    definition_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    is_template: bool = False
    graph: dict[str, Any] = {}


class UpdateWorkflowDefRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: dict[str, Any] | None = None
    is_template: bool | None = None
    enabled: bool | None = None


@router.post("/workflow-definitions", status_code=201)
async def create_workflow_definition(
    body: CreateWorkflowDefRequest,
    request: Request,
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> dict[str, Any]:
    """Create a new workflow definition."""
    await _ensure_seeded(store)
    existing = await store.get(body.definition_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Definition already exists")
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "definition_id": body.definition_id,
        "name": body.name,
        "description": body.description,
        "is_template": body.is_template,
        "graph": body.graph,
        "created_at": now,
        "updated_at": now,
    }
    await store.put(body.definition_id, entry)
    await dispatch_event(
        request,
        WorkflowDefinitionCreated(payload={"resource_id": body.definition_id}),
        stream_id=f"workflow_definition:{body.definition_id}",
    )
    return entry


@router.get("/workflow-definitions")
async def list_workflow_definitions(
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> list[dict[str, Any]]:
    """List all workflow definitions and templates."""
    await _ensure_seeded(store)
    return await store.list_all()


@router.get("/workflow-definitions/templates")
async def list_templates(
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> list[dict[str, Any]]:
    """List only workflow templates."""
    await _ensure_seeded(store)
    all_defs = await store.list_all()
    return [d for d in all_defs if d.get("is_template")]


@router.get("/workflow-definitions/{definition_id}")
async def get_workflow_definition(
    definition_id: str,
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> dict[str, Any]:
    """Get a specific workflow definition."""
    await _ensure_seeded(store)
    entry = await store.get(definition_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    return entry


@router.put("/workflow-definitions/{definition_id}")
async def update_workflow_definition(
    definition_id: str,
    body: UpdateWorkflowDefRequest,
    request: Request,
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> dict[str, Any]:
    """Update a workflow definition (save graph JSON)."""
    await _ensure_seeded(store)
    entry = await store.get(definition_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    for key, value in body.model_dump(exclude_none=True).items():
        entry[key] = value
    entry["updated_at"] = datetime.now(UTC).isoformat()
    await store.put(definition_id, entry)
    await dispatch_event(
        request,
        WorkflowDefinitionUpdated(payload={"resource_id": definition_id}),
        stream_id=f"workflow_definition:{definition_id}",
    )
    return entry


@router.patch("/workflow-definitions/{definition_id}/toggle")
async def toggle_workflow_definition(
    definition_id: str,
    request: Request,
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> dict[str, Any]:
    """Toggle the enabled state of a workflow definition."""
    await _ensure_seeded(store)
    entry = await store.get(definition_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    entry["enabled"] = not entry.get("enabled", True)
    entry["updated_at"] = datetime.now(UTC).isoformat()
    await store.put(definition_id, entry)
    await dispatch_event(
        request,
        WorkflowDefinitionUpdated(payload={"resource_id": definition_id}),
        stream_id=f"workflow_definition:{definition_id}",
    )
    return entry


@router.delete("/workflow-definitions/{definition_id}", status_code=204)
async def delete_workflow_definition(
    definition_id: str,
    request: Request,
    store: InMemoryWorkflowDefinitionStore = Depends(  # noqa: B008
        workflow_definition_store_provider
    ),
) -> None:
    """Delete a workflow definition."""
    await _ensure_seeded(store)
    entry = await store.get(definition_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    await store.remove(definition_id)
    await dispatch_event(
        request,
        WorkflowDefinitionRemoved(payload={"resource_id": definition_id}),
        stream_id=f"workflow_definition:{definition_id}",
    )
