"""In-memory sandbox credential store."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.sandbox_credentials_api.types import SandboxCredential


def _to_dict(c: SandboxCredential) -> dict[str, Any]:
    d = asdict(c)
    d["scopes"] = list(c.scopes)
    d["issued_at"] = c.issued_at.isoformat()
    d["expires_at"] = c.expires_at.isoformat()
    if d["revoked_at"] is not None:
        d["revoked_at"] = c.revoked_at.isoformat() if c.revoked_at else None
    return d


class InMemorySandboxCredentialStore:
    """Simple in-memory store for ephemeral sandbox credentials."""

    def __init__(self) -> None:
        self._items: dict[str, SandboxCredential] = {}

    async def add(self, credential: SandboxCredential) -> dict[str, Any]:
        self._items[credential.id] = credential
        return _to_dict(credential)

    async def get(self, credential_id: str) -> dict[str, Any] | None:
        c = self._items.get(credential_id)
        if c is None:
            return None
        return _to_dict(c)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(c) for c in self._items.values()]

    async def list_by_sandbox(self, sandbox_id: str) -> list[dict[str, Any]]:
        return [_to_dict(c) for c in self._items.values() if c.sandbox_id == sandbox_id]

    async def update(self, credential_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from lintel.sandbox_credentials_api.types import SandboxCredential

        c = self._items.get(credential_id)
        if c is None:
            return None
        data = asdict(c)
        data.update(updates)
        if isinstance(data.get("scopes"), list):
            data["scopes"] = tuple(data["scopes"])
        updated = SandboxCredential(**data)
        self._items[credential_id] = updated
        return _to_dict(updated)

    async def revoke_all_for_sandbox(self, sandbox_id: str) -> int:
        """Revoke all active credentials for a sandbox. Returns count revoked."""
        from lintel.sandbox_credentials_api.types import (
            SandboxCredential,
            SandboxCredentialStatus,
        )

        count = 0
        now = datetime.now(UTC)
        for cid, c in list(self._items.items()):
            if c.sandbox_id == sandbox_id and c.status == SandboxCredentialStatus.ACTIVE:
                data = asdict(c)
                data["status"] = SandboxCredentialStatus.REVOKED
                data["revoked_at"] = now
                self._items[cid] = SandboxCredential(**data)
                count += 1
        return count

    async def remove(self, credential_id: str) -> bool:
        if credential_id not in self._items:
            return False
        del self._items[credential_id]
        return True
