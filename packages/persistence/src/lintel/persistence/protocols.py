"""Persistence protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lintel.persistence.types import Credential


class CredentialStore(Protocol):
    """Secure storage for SSH keys and GitHub tokens."""

    async def store(
        self,
        credential_id: str,
        credential_type: str,
        name: str,
        secret: str,
        repo_ids: list[str] | None = None,
    ) -> Credential: ...

    async def get(self, credential_id: str) -> Credential | None: ...

    async def list_all(self) -> list[Credential]: ...

    async def list_by_repo(self, repo_id: str) -> list[Credential]: ...

    async def get_secret(self, credential_id: str) -> str | None: ...

    async def revoke(self, credential_id: str) -> None: ...
