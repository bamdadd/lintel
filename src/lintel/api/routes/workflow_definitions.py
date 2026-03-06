"""Workflow template and graph definition CRUD endpoints."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


def get_workflow_defs(request: Request) -> dict[str, dict[str, Any]]:
    """Get workflow definitions store from app state."""
    if not hasattr(request.app.state, "workflow_definitions"):
        request.app.state.workflow_definitions = {
            "feature_to_pr": {
                "definition_id": "feature_to_pr",
                "name": "Feature to PR",
                "description": "End-to-end feature implementation workflow",
                "is_template": True,
                "graph": {
                    "nodes": [
                        "ingest",
                        "route",
                        "plan",
                        "approval_gate_spec",
                        "implement",
                        "review",
                        "approval_gate_merge",
                        "close",
                    ],
                    "edges": [
                        ["ingest", "route"],
                        ["plan", "approval_gate_spec"],
                        ["approval_gate_spec", "implement"],
                        ["implement", "review"],
                        ["review", "approval_gate_merge"],
                        ["approval_gate_merge", "close"],
                    ],
                    "conditional_edges": [
                        {
                            "source": "route",
                            "targets": {"plan": "plan", "close": "close"},
                        }
                    ],
                    "entry_point": "ingest",
                    "interrupt_before": [
                        "approval_gate_spec",
                        "approval_gate_merge",
                    ],
                },
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        }
    return request.app.state.workflow_definitions  # type: ignore[no-any-return]


class CreateWorkflowDefRequest(BaseModel):
    definition_id: str
    name: str
    description: str = ""
    is_template: bool = False
    graph: dict[str, Any] = {}


class UpdateWorkflowDefRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: dict[str, Any] | None = None
    is_template: bool | None = None


@router.post("/workflow-definitions", status_code=201)
async def create_workflow_definition(
    body: CreateWorkflowDefRequest, request: Request
) -> dict[str, Any]:
    """Create a new workflow definition."""
    defs = get_workflow_defs(request)
    if body.definition_id in defs:
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
    defs[body.definition_id] = entry
    return entry


@router.get("/workflow-definitions")
async def list_workflow_definitions(
    request: Request,
) -> list[dict[str, Any]]:
    """List all workflow definitions and templates."""
    return list(get_workflow_defs(request).values())


@router.get("/workflow-definitions/templates")
async def list_templates(request: Request) -> list[dict[str, Any]]:
    """List only workflow templates."""
    return [d for d in get_workflow_defs(request).values() if d.get("is_template")]


@router.get("/workflow-definitions/{definition_id}")
async def get_workflow_definition(definition_id: str, request: Request) -> dict[str, Any]:
    """Get a specific workflow definition."""
    defs = get_workflow_defs(request)
    if definition_id not in defs:
        raise HTTPException(status_code=404, detail="Definition not found")
    return defs[definition_id]


@router.put("/workflow-definitions/{definition_id}")
async def update_workflow_definition(
    definition_id: str, body: UpdateWorkflowDefRequest, request: Request
) -> dict[str, Any]:
    """Update a workflow definition (save graph JSON)."""
    defs = get_workflow_defs(request)
    if definition_id not in defs:
        raise HTTPException(status_code=404, detail="Definition not found")
    entry = defs[definition_id]
    for key, value in body.model_dump(exclude_none=True).items():
        entry[key] = value
    entry["updated_at"] = datetime.now(UTC).isoformat()
    return entry


@router.delete("/workflow-definitions/{definition_id}", status_code=204)
async def delete_workflow_definition(definition_id: str, request: Request) -> None:
    """Delete a workflow definition."""
    defs = get_workflow_defs(request)
    if definition_id not in defs:
        raise HTTPException(status_code=404, detail="Definition not found")
    del defs[definition_id]
