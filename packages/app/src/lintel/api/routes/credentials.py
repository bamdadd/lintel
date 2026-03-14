"""Credential management endpoints (SSH keys and GitHub tokens)."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.contracts.events import CredentialRevoked, CredentialStored
from lintel.contracts.types import Credential, CredentialType
from lintel.domain.event_dispatcher import dispatch_event

router = APIRouter()


class InMemoryCredentialStore:
    """In-memory credential store. Secrets are masked on read."""

    def __init__(self) -> None:
        self._creds: dict[str, Credential] = {}
        self._secrets: dict[str, str] = {}

    async def store(
        self,
        credential_id: str,
        credential_type: str,
        name: str,
        secret: str,
        repo_ids: list[str] | None = None,
    ) -> Credential:
        cred = Credential(
            credential_id=credential_id,
            credential_type=CredentialType(credential_type),
            name=name,
            repo_ids=frozenset(repo_ids or []),
        )
        self._creds[credential_id] = cred
        self._secrets[credential_id] = secret
        return cred

    async def get(self, credential_id: str) -> Credential | None:
        return self._creds.get(credential_id)

    async def list_all(self) -> list[Credential]:
        return list(self._creds.values())

    async def get_secret(self, credential_id: str) -> str | None:
        return self._secrets.get(credential_id)

    async def list_by_repo(self, repo_id: str) -> list[Credential]:
        return [c for c in self._creds.values() if not c.repo_ids or repo_id in c.repo_ids]

    async def revoke(self, credential_id: str) -> None:
        if credential_id not in self._creds:
            msg = f"Credential {credential_id} not found"
            raise KeyError(msg)
        del self._creds[credential_id]
        self._secrets.pop(credential_id, None)


def get_credential_store(request: Request) -> InMemoryCredentialStore:
    """Kept for backward compat."""
    return request.app.state.credential_store  # type: ignore[no-any-return]


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
@inject
async def store_credential(
    request: Request,
    body: StoreCredentialRequest,
    store: InMemoryCredentialStore = Depends(Provide[AppContainer.credential_store]),  # noqa: B008
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
@inject
async def list_credentials(
    store: InMemoryCredentialStore = Depends(Provide[AppContainer.credential_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all credentials (secrets masked)."""
    creds = await store.list_all()
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.get("/credentials/{credential_id}")
@inject
async def get_credential(
    credential_id: str,
    store: InMemoryCredentialStore = Depends(Provide[AppContainer.credential_store]),  # noqa: B008
) -> dict[str, Any]:
    """Get a credential by ID (secret masked)."""
    cred = await store.get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {**asdict(cred), "repo_ids": list(cred.repo_ids)}


@router.get("/credentials/repo/{repo_id}")
@inject
async def list_credentials_for_repo(
    repo_id: str,
    store: InMemoryCredentialStore = Depends(Provide[AppContainer.credential_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    """List credentials applicable to a specific repo."""
    creds = await store.list_by_repo(repo_id)
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.delete("/credentials/{credential_id}", status_code=204)
@inject
async def revoke_credential(
    credential_id: str,
    request: Request,
    store: InMemoryCredentialStore = Depends(Provide[AppContainer.credential_store]),  # noqa: B008
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
