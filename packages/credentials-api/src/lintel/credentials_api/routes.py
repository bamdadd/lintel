"""Credential management endpoints (SSH keys and GitHub tokens)."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.credentials_api.store import InMemoryCredentialStore
from lintel.persistence.events import CredentialRevoked, CredentialStored
from lintel.persistence.types import CredentialType

router = APIRouter()

credential_store_provider: StoreProvider = StoreProvider()


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]


class StoreCredentialRequest(BaseModel):
    credential_id: str = Field(default_factory=lambda: str(uuid4()))
    credential_type: CredentialType
    name: str
    secret: str
    repo_ids: list[str] = []


class UpdateCredentialRequest(BaseModel):
    name: str | None = None
    repo_ids: list[str] | None = None


@router.post("/credentials", status_code=201)
async def store_credential(
    request: Request,
    body: StoreCredentialRequest,
    store: InMemoryCredentialStore = Depends(credential_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Store an SSH key or GitHub token."""
    existing = await store.get(body.credential_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Credential already exists")
    cred = await store.store(
        credential_id=body.credential_id,
        credential_type=body.credential_type.value,
        name=body.name,
        secret=body.secret,
        repo_ids=body.repo_ids,
    )
    await dispatch_event(
        request,
        CredentialStored(
            payload={
                "resource_id": body.credential_id,
                "name": body.name,
                "credential_type": body.credential_type,
            }
        ),
        stream_id=f"credential:{body.credential_id}",
    )
    result = asdict(cred)
    result["secret_preview"] = _mask_secret(body.secret)
    result["repo_ids"] = list(cred.repo_ids)
    return result


@router.get("/credentials")
async def list_credentials(
    store: InMemoryCredentialStore = Depends(credential_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all credentials (secrets masked)."""
    creds = await store.list_all()
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.get("/credentials/{credential_id}")
async def get_credential(
    credential_id: str,
    store: InMemoryCredentialStore = Depends(credential_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a credential by ID (secret masked)."""
    cred = await store.get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {**asdict(cred), "repo_ids": list(cred.repo_ids)}


@router.get("/credentials/repo/{repo_id}")
async def list_credentials_for_repo(
    repo_id: str,
    store: InMemoryCredentialStore = Depends(credential_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List credentials applicable to a specific repo."""
    creds = await store.list_by_repo(repo_id)
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.delete("/credentials/{credential_id}", status_code=204)
async def revoke_credential(
    credential_id: str,
    request: Request,
    store: InMemoryCredentialStore = Depends(credential_store_provider),  # noqa: B008
) -> None:
    """Revoke and delete a credential."""
    cred = await store.get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    await store.revoke(credential_id)
    await dispatch_event(
        request,
        CredentialRevoked(payload={"resource_id": credential_id}),
        stream_id=f"credential:{credential_id}",
    )
