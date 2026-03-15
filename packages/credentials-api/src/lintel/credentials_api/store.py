"""In-memory credential store."""

from lintel.persistence.types import Credential, CredentialType


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
