"""Credential management endpoints (SSH keys and GitHub tokens)."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import Credential, CredentialType

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

    async def list_by_repo(self, repo_id: str) -> list[Credential]:
        return [c for c in self._creds.values() if not c.repo_ids or repo_id in c.repo_ids]

    async def revoke(self, credential_id: str) -> None:
        if credential_id not in self._creds:
            msg = f"Credential {credential_id} not found"
            raise KeyError(msg)
        del self._creds[credential_id]
        self._secrets.pop(credential_id, None)


def get_credential_store(request: Request) -> InMemoryCredentialStore:
    """Get credential store from app state."""
    return request.app.state.credential_store  # type: ignore[no-any-return]


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]


class StoreCredentialRequest(BaseModel):
    credential_id: str
    credential_type: CredentialType
    name: str
    secret: str
    repo_ids: list[str] = []


class UpdateCredentialRequest(BaseModel):
    name: str | None = None
    repo_ids: list[str] | None = None


@router.post("/credentials", status_code=201)
async def store_credential(
    body: StoreCredentialRequest,
    store: Annotated[InMemoryCredentialStore, Depends(get_credential_store)],
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
    result = asdict(cred)
    result["secret_preview"] = _mask_secret(body.secret)
    result["repo_ids"] = list(cred.repo_ids)
    return result


@router.get("/credentials")
async def list_credentials(
    store: Annotated[InMemoryCredentialStore, Depends(get_credential_store)],
) -> list[dict[str, Any]]:
    """List all credentials (secrets masked)."""
    creds = await store.list_all()
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.get("/credentials/{credential_id}")
async def get_credential(
    credential_id: str,
    store: Annotated[InMemoryCredentialStore, Depends(get_credential_store)],
) -> dict[str, Any]:
    """Get a credential by ID (secret masked)."""
    cred = await store.get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {**asdict(cred), "repo_ids": list(cred.repo_ids)}


@router.get("/credentials/repo/{repo_id}")
async def list_credentials_for_repo(
    repo_id: str,
    store: Annotated[InMemoryCredentialStore, Depends(get_credential_store)],
) -> list[dict[str, Any]]:
    """List credentials applicable to a specific repo."""
    creds = await store.list_by_repo(repo_id)
    return [{**asdict(c), "repo_ids": list(c.repo_ids)} for c in creds]


@router.delete("/credentials/{credential_id}", status_code=204)
async def revoke_credential(
    credential_id: str,
    store: Annotated[InMemoryCredentialStore, Depends(get_credential_store)],
) -> None:
    """Revoke and delete a credential."""
    cred = await store.get(credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    await store.revoke(credential_id)
