"""Regulation-to-policy generation trigger endpoint.

POST /compliance/generate-policies triggers the regulation_to_policy
workflow for one or more regulations within a project. The caller provides:
- regulation_ids: which regulations to convert
- industry_context: "it", "health", "finance", or "general"
- additional_context: free-text context from the user
- project_id: the project these policies belong to

The endpoint creates a PolicyGenerationRun record and returns it
immediately. The actual generation happens asynchronously via the
regulation_to_policy workflow.
"""

import asyncio
import json
import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.contracts.types import ThreadRef
from lintel.domain.events import PolicyGenerationStarted
from lintel.domain.types import PolicyGenerationRun, PolicyGenerationStatus
from lintel.workflows.commands import StartWorkflow

logger = logging.getLogger(__name__)

router = APIRouter()

policy_generation_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class GeneratePoliciesRequest(BaseModel):
    """Request to trigger regulation-to-policy generation."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    regulation_ids: list[str]
    industry_context: str = "general"  # it, health, finance, general
    additional_context: str = ""


class UpdatePolicyGenerationRequest(BaseModel):
    """Update a policy generation run (e.g. after workflow completes)."""

    status: PolicyGenerationStatus | None = None
    generated_policy_ids: list[str] | None = None
    generated_procedure_ids: list[str] | None = None
    assumptions: list[str] | None = None
    questions: list[str] | None = None
    action_items: list[str] | None = None
    summary: str | None = None
    error: str | None = None
    completed_at: str | None = None


@router.post("/compliance/generate-policies", status_code=201)
async def trigger_policy_generation(
    request: Request,
    body: GeneratePoliciesRequest,
    store: Annotated[ComplianceStore, Depends(policy_generation_store_provider)],
) -> dict[str, Any]:
    """Trigger regulation-to-policy generation for a project.

    Creates a PolicyGenerationRun and kicks off the workflow. The run
    tracks progress, generated artefacts, assumptions, questions and
    action items.
    """
    if not body.regulation_ids:
        raise HTTPException(status_code=400, detail="At least one regulation_id is required")

    if body.industry_context not in ("it", "health", "finance", "general"):
        raise HTTPException(
            status_code=400,
            detail="industry_context must be one of: it, health, finance, general",
        )

    existing = await store.get(body.run_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Generation run already exists")

    run = PolicyGenerationRun(
        run_id=body.run_id,
        project_id=body.project_id,
        regulation_ids=tuple(body.regulation_ids),
        status=PolicyGenerationStatus.PENDING,
        industry_context=body.industry_context,
        additional_context=body.additional_context,
    )
    result = await store.add(run)
    await dispatch_event(
        request,
        PolicyGenerationStarted(
            payload={
                "resource_id": body.run_id,
                "project_id": body.project_id,
                "regulation_ids": body.regulation_ids,
                "industry_context": body.industry_context,
            }
        ),
        stream_id=f"policy_generation:{body.run_id}",
    )

    # Dispatch the regulation_to_policy workflow
    dispatcher = getattr(request.app.state, "command_dispatcher", None)
    if dispatcher:
        trigger_context = json.dumps(
            {
                "regulation_ids": body.regulation_ids,
                "industry_context": body.industry_context,
                "additional_context": body.additional_context,
            }
        )
        command = StartWorkflow(
            thread_ref=ThreadRef(
                workspace_id="pipeline",
                channel_id="compliance",
                thread_ts=body.run_id,
            ),
            workflow_type="regulation_to_policy",
            project_id=body.project_id,
            run_id=body.run_id,
            trigger_context=trigger_context,
        )
        asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
        logger.info("regulation_to_policy_workflow_dispatched: %s", body.run_id)

    return result


@router.get("/compliance/policy-generations")
async def list_policy_generations(
    store: Annotated[ComplianceStore, Depends(policy_generation_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all policy generation runs, optionally filtered by project."""
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/compliance/policy-generations/{run_id}")
async def get_policy_generation(
    run_id: str,
    store: Annotated[ComplianceStore, Depends(policy_generation_store_provider)],
) -> dict[str, Any]:
    """Get a single policy generation run by ID."""
    item = await store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Policy generation run not found")
    return item


@router.patch("/compliance/policy-generations/{run_id}")
async def update_policy_generation(
    request: Request,
    run_id: str,
    body: UpdatePolicyGenerationRequest,
    store: Annotated[ComplianceStore, Depends(policy_generation_store_provider)],
) -> dict[str, Any]:
    """Update a policy generation run (typically called by the workflow)."""
    updates = body.model_dump(exclude_none=True)
    for key in (
        "generated_policy_ids",
        "generated_procedure_ids",
        "assumptions",
        "questions",
        "action_items",
    ):
        if key in updates:
            updates[key] = list(updates[key])
    result = await store.update(run_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Policy generation run not found")
    return result
