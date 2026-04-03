"""Visual verification CRUD endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    VisualVerificationCreated,
    VisualVerificationStatusChanged,
)
from lintel.visual_verification_api.store import InMemoryVisualVerificationStore  # noqa: TC001
from lintel.visual_verification_api.types import VerificationStatus, VisualVerification

router = APIRouter()

verification_store_provider: StoreProvider[InMemoryVisualVerificationStore] = StoreProvider()


class CreateVerificationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_run_id: str
    stage_name: str
    before_url: str = ""
    after_url: str = ""
    diff_url: str = ""
    status: VerificationStatus = VerificationStatus.PENDING


class UpdateVerificationRequest(BaseModel):
    before_url: str | None = None
    after_url: str | None = None
    diff_url: str | None = None
    status: VerificationStatus | None = None


@router.post("/visual-verifications", status_code=201)
async def create_verification(
    request: Request,
    body: CreateVerificationRequest,
    store: Annotated[InMemoryVisualVerificationStore, Depends(verification_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Visual verification already exists")
    verification = VisualVerification(
        id=body.id,
        pipeline_run_id=body.pipeline_run_id,
        stage_name=body.stage_name,
        before_url=body.before_url,
        after_url=body.after_url,
        diff_url=body.diff_url,
        status=body.status,
    )
    result = await store.add(verification)
    await dispatch_event(
        request,
        VisualVerificationCreated(
            payload={"resource_id": body.id, "pipeline_run_id": body.pipeline_run_id},
        ),
        stream_id=f"visual-verification:{body.id}",
    )
    return result


@router.get("/visual-verifications")
async def list_verifications(
    store: Annotated[InMemoryVisualVerificationStore, Depends(verification_store_provider)],
    pipeline_run_id: str | None = None,
) -> list[dict[str, Any]]:
    if pipeline_run_id:
        return await store.list_by_pipeline(pipeline_run_id)
    return await store.list_all()


@router.get("/visual-verifications/{verification_id}")
async def get_verification(
    verification_id: str,
    store: Annotated[InMemoryVisualVerificationStore, Depends(verification_store_provider)],
) -> dict[str, Any]:
    item = await store.get(verification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Visual verification not found")
    return item


@router.patch("/visual-verifications/{verification_id}")
async def update_verification(
    request: Request,
    verification_id: str,
    body: UpdateVerificationRequest,
    store: Annotated[InMemoryVisualVerificationStore, Depends(verification_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(verification_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Visual verification not found")
    if body.status is not None:
        await dispatch_event(
            request,
            VisualVerificationStatusChanged(
                payload={
                    "resource_id": verification_id,
                    "status": body.status.value,
                },
            ),
            stream_id=f"visual-verification:{verification_id}",
        )
    return result


@router.delete("/visual-verifications/{verification_id}", status_code=204)
async def delete_verification(
    verification_id: str,
    store: Annotated[InMemoryVisualVerificationStore, Depends(verification_store_provider)],
) -> None:
    if not await store.remove(verification_id):
        raise HTTPException(status_code=404, detail="Visual verification not found")
