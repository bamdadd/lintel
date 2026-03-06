"""Workflow operation endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lintel.api.deps import get_thread_status_projection
from lintel.contracts.commands import ProcessIncomingMessage, StartWorkflow
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection

router = APIRouter()


class StartWorkflowRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    workflow_type: str


class ProcessMessageRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    raw_text: str
    sender_id: str
    sender_name: str


@router.post("/workflows", status_code=201)
async def start_workflow(
    body: StartWorkflowRequest,
) -> dict[str, Any]:
    """Start a new workflow."""
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = StartWorkflow(
        thread_ref=thread_ref,
        workflow_type=body.workflow_type,
    )
    return asdict(command)


@router.get("/workflows")
async def list_workflows(
    projection: Annotated[ThreadStatusProjection, Depends(get_thread_status_projection)],
) -> list[dict[str, Any]]:
    """List all workflows."""
    return projection.get_all()


@router.get("/workflows/{stream_id}")
async def get_workflow(
    stream_id: str,
    projection: Annotated[ThreadStatusProjection, Depends(get_thread_status_projection)],
) -> dict[str, Any]:
    """Get a single workflow status."""
    all_workflows = projection.get_all()
    for workflow in all_workflows:
        if workflow.get("stream_id") == stream_id:
            return workflow
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/workflows/messages", status_code=201)
async def process_message(
    body: ProcessMessageRequest,
) -> dict[str, Any]:
    """Process an incoming message."""
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = ProcessIncomingMessage(
        thread_ref=thread_ref,
        raw_text=body.raw_text,
        sender_id=body.sender_id,
        sender_name=body.sender_name,
    )
    return asdict(command)
