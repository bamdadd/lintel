"""Workflow Blueprint CRUD endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    WorkflowBlueprintActivated,
    WorkflowBlueprintCreated,
    WorkflowBlueprintDeactivated,
    WorkflowBlueprintRemoved,
    WorkflowBlueprintUpdated,
)
from lintel.domain.types import BlueprintNode, BlueprintNodeType, WorkflowBlueprint
from lintel.workflow_blueprints_api.store import InMemoryWorkflowBlueprintStore  # noqa: TC001

router = APIRouter()

blueprint_store_provider: StoreProvider[InMemoryWorkflowBlueprintStore] = StoreProvider()


# --- Request / Response models ---


class NodeModel(BaseModel):
    node_id: str = ""
    name: str
    node_type: BlueprintNodeType
    description: str = ""
    config: dict[str, object] | None = None
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0


class CreateBlueprintRequest(BaseModel):
    name: str
    description: str = ""
    team_id: str = ""
    nodes: list[NodeModel] = Field(default_factory=list)
    version: str = "1.0"
    active: bool = True
    project_id: str = ""


class UpdateBlueprintRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    team_id: str | None = None
    nodes: list[NodeModel] | None = None
    version: str | None = None
    active: bool | None = None
    project_id: str | None = None


class NodeTypeInfo(BaseModel):
    value: str
    description: str


# --- Blueprint endpoints ---


@router.post("/workflow-blueprints", status_code=201)
async def create_blueprint(
    request: Request,
    body: CreateBlueprintRequest,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> dict[str, Any]:
    blueprint_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    nodes = tuple(
        BlueprintNode(
            node_id=n.node_id or str(uuid4()),
            name=n.name,
            node_type=n.node_type,
            description=n.description,
            config=n.config,
            depends_on=tuple(n.depends_on),
            timeout_seconds=n.timeout_seconds,
            retry_count=n.retry_count,
        )
        for n in body.nodes
    )
    bp = WorkflowBlueprint(
        blueprint_id=blueprint_id,
        name=body.name,
        description=body.description,
        team_id=body.team_id,
        nodes=nodes,
        version=body.version,
        active=body.active,
        project_id=body.project_id,
        created_at=now,
        updated_at=now,
    )
    result = await store.add(bp)
    await dispatch_event(
        request,
        WorkflowBlueprintCreated(
            payload={"resource_id": blueprint_id, "name": body.name},
        ),
        stream_id=f"workflow-blueprint:{blueprint_id}",
    )
    return result


@router.get("/workflow-blueprints")
async def list_blueprints(
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/workflow-blueprints/node-types")
async def list_node_types() -> list[NodeTypeInfo]:
    descriptions = {
        BlueprintNodeType.DETERMINISTIC: "A deterministic step with fixed logic",
        BlueprintNodeType.AGENTIC: "An AI agent-powered step",
        BlueprintNodeType.HUMAN_REVIEW: "A step requiring human review/approval",
        BlueprintNodeType.CONDITIONAL: "A branching step based on conditions",
        BlueprintNodeType.PARALLEL: "A step that runs sub-nodes in parallel",
    }
    return [NodeTypeInfo(value=nt.value, description=descriptions[nt]) for nt in BlueprintNodeType]


@router.get("/workflow-blueprints/{blueprint_id}")
async def get_blueprint(
    blueprint_id: str,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> dict[str, Any]:
    item = await store.get(blueprint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    return item


@router.patch("/workflow-blueprints/{blueprint_id}")
async def update_blueprint(
    request: Request,
    blueprint_id: str,
    body: UpdateBlueprintRequest,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> dict[str, Any]:
    updates: dict[str, Any] = body.model_dump(exclude_none=True)
    if "nodes" in updates:
        updates["nodes"] = [n.model_dump() for n in body.nodes or []]
    updates["updated_at"] = datetime.now(UTC).isoformat()
    result = await store.update(blueprint_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    await dispatch_event(
        request,
        WorkflowBlueprintUpdated(payload={"resource_id": blueprint_id}),
        stream_id=f"workflow-blueprint:{blueprint_id}",
    )
    return result


@router.delete("/workflow-blueprints/{blueprint_id}", status_code=204)
async def delete_blueprint(
    request: Request,
    blueprint_id: str,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> None:
    if not await store.remove(blueprint_id):
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    await dispatch_event(
        request,
        WorkflowBlueprintRemoved(payload={"resource_id": blueprint_id}),
        stream_id=f"workflow-blueprint:{blueprint_id}",
    )


@router.post("/workflow-blueprints/{blueprint_id}/activate")
async def activate_blueprint(
    request: Request,
    blueprint_id: str,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> dict[str, Any]:
    result = await store.update(
        blueprint_id,
        {"active": True, "updated_at": datetime.now(UTC).isoformat()},
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    await dispatch_event(
        request,
        WorkflowBlueprintActivated(payload={"resource_id": blueprint_id}),
        stream_id=f"workflow-blueprint:{blueprint_id}",
    )
    return result


@router.post("/workflow-blueprints/{blueprint_id}/deactivate")
async def deactivate_blueprint(
    request: Request,
    blueprint_id: str,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> dict[str, Any]:
    result = await store.update(
        blueprint_id,
        {"active": False, "updated_at": datetime.now(UTC).isoformat()},
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    await dispatch_event(
        request,
        WorkflowBlueprintDeactivated(payload={"resource_id": blueprint_id}),
        stream_id=f"workflow-blueprint:{blueprint_id}",
    )
    return result


@router.get("/workflow-blueprints/{blueprint_id}/nodes")
async def list_blueprint_nodes(
    blueprint_id: str,
    store: Annotated[InMemoryWorkflowBlueprintStore, Depends(blueprint_store_provider)],
) -> list[dict[str, Any]]:
    item = await store.get(blueprint_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Workflow blueprint not found")
    return item["nodes"]
