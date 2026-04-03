"""Sandbox credential CRUD endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import SandboxCredentialIssued, SandboxCredentialRevoked
from lintel.sandbox_credentials_api.store import InMemorySandboxCredentialStore  # noqa: TC001
from lintel.sandbox_credentials_api.types import (
    SandboxCredential,
    SandboxCredentialStatus,
    SandboxCredentialType,
)

router = APIRouter()

sandbox_credential_store_provider: StoreProvider[InMemorySandboxCredentialStore] = StoreProvider()


class IssueCredentialRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    sandbox_id: str
    credential_type: SandboxCredentialType
    name: str
    scopes: list[str] = []
    ttl_seconds: int = 3600


class UpdateCredentialRequest(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None


@router.post("/sandbox-credentials", status_code=201)
async def issue_credential(
    request: Request,
    body: IssueCredentialRequest,
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Credential already exists")
    now = datetime.now(UTC)
    credential = SandboxCredential(
        id=body.id,
        sandbox_id=body.sandbox_id,
        credential_type=body.credential_type,
        name=body.name,
        scopes=tuple(body.scopes),
        issued_at=now,
        expires_at=now + timedelta(seconds=body.ttl_seconds),
    )
    result = await store.add(credential)
    await dispatch_event(
        request,
        SandboxCredentialIssued(
            payload={
                "resource_id": body.id,
                "sandbox_id": body.sandbox_id,
                "credential_type": body.credential_type.value,
            },
        ),
        stream_id=f"sandbox-credential:{body.id}",
    )
    return result


@router.get("/sandbox-credentials")
async def list_credentials(
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
    sandbox_id: str | None = None,
) -> list[dict[str, Any]]:
    if sandbox_id:
        return await store.list_by_sandbox(sandbox_id)
    return await store.list_all()


@router.get("/sandbox-credentials/{credential_id}")
async def get_credential(
    credential_id: str,
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
) -> dict[str, Any]:
    item = await store.get(credential_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sandbox credential not found")
    return item


@router.patch("/sandbox-credentials/{credential_id}")
async def update_credential(
    credential_id: str,
    body: UpdateCredentialRequest,
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "scopes" in updates:
        updates["scopes"] = tuple(updates["scopes"])
    result = await store.update(credential_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Sandbox credential not found")
    return result


@router.post("/sandbox-credentials/{credential_id}/revoke")
async def revoke_credential(
    request: Request,
    credential_id: str,
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
) -> dict[str, Any]:
    item = await store.get(credential_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sandbox credential not found")
    if item["status"] != SandboxCredentialStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Credential is not active")
    result = await store.update(
        credential_id,
        {"status": SandboxCredentialStatus.REVOKED, "revoked_at": datetime.now(UTC)},
    )
    await dispatch_event(
        request,
        SandboxCredentialRevoked(
            payload={"resource_id": credential_id, "sandbox_id": item["sandbox_id"]},
        ),
        stream_id=f"sandbox-credential:{credential_id}",
    )
    return result  # type: ignore[return-value]


@router.post("/sandbox-credentials/sandbox/{sandbox_id}/revoke-all")
async def revoke_all_for_sandbox(
    request: Request,
    sandbox_id: str,
    store: Annotated[InMemorySandboxCredentialStore, Depends(sandbox_credential_store_provider)],
) -> dict[str, Any]:
    count = await store.revoke_all_for_sandbox(sandbox_id)
    if count > 0:
        await dispatch_event(
            request,
            SandboxCredentialRevoked(
                payload={"resource_id": sandbox_id, "revoked_count": count},
            ),
            stream_id=f"sandbox:{sandbox_id}",
        )
    return {"sandbox_id": sandbox_id, "revoked_count": count}
