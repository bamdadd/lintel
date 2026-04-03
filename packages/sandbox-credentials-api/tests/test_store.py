"""Tests for InMemorySandboxCredentialStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lintel.sandbox_credentials_api.store import InMemorySandboxCredentialStore
from lintel.sandbox_credentials_api.types import (
    SandboxCredential,
    SandboxCredentialStatus,
    SandboxCredentialType,
)


@pytest.fixture()
def store() -> InMemorySandboxCredentialStore:
    return InMemorySandboxCredentialStore()


def _make_credential(
    cred_id: str = "cred-1",
    sandbox_id: str = "sbx-1",
) -> SandboxCredential:
    now = datetime.now(UTC)
    return SandboxCredential(
        id=cred_id,
        sandbox_id=sandbox_id,
        credential_type=SandboxCredentialType.API_KEY,
        name="Test Key",
        scopes=("read", "write"),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )


class TestAdd:
    async def test_add_and_get(self, store: InMemorySandboxCredentialStore) -> None:
        cred = _make_credential()
        result = await store.add(cred)
        assert result["id"] == "cred-1"
        assert result["scopes"] == ["read", "write"]

        fetched = await store.get("cred-1")
        assert fetched is not None
        assert fetched["id"] == "cred-1"


class TestList:
    async def test_list_all(self, store: InMemorySandboxCredentialStore) -> None:
        await store.add(_make_credential("c1"))
        await store.add(_make_credential("c2"))
        items = await store.list_all()
        assert len(items) == 2

    async def test_list_by_sandbox(self, store: InMemorySandboxCredentialStore) -> None:
        await store.add(_make_credential("c1", "sbx-1"))
        await store.add(_make_credential("c2", "sbx-2"))
        items = await store.list_by_sandbox("sbx-1")
        assert len(items) == 1
        assert items[0]["sandbox_id"] == "sbx-1"


class TestUpdate:
    async def test_update_name(self, store: InMemorySandboxCredentialStore) -> None:
        await store.add(_make_credential())
        result = await store.update("cred-1", {"name": "Updated"})
        assert result is not None
        assert result["name"] == "Updated"

    async def test_update_not_found(self, store: InMemorySandboxCredentialStore) -> None:
        result = await store.update("nope", {"name": "X"})
        assert result is None


class TestRevoke:
    async def test_revoke_all_for_sandbox(self, store: InMemorySandboxCredentialStore) -> None:
        await store.add(_make_credential("c1", "sbx-1"))
        await store.add(_make_credential("c2", "sbx-1"))
        await store.add(_make_credential("c3", "sbx-2"))
        count = await store.revoke_all_for_sandbox("sbx-1")
        assert count == 2

        # Verify they are revoked
        items = await store.list_by_sandbox("sbx-1")
        for item in items:
            assert item["status"] == SandboxCredentialStatus.REVOKED

        # sbx-2 credential is still active
        sbx2_items = await store.list_by_sandbox("sbx-2")
        assert sbx2_items[0]["status"] == SandboxCredentialStatus.ACTIVE


class TestRemove:
    async def test_remove_existing(self, store: InMemorySandboxCredentialStore) -> None:
        await store.add(_make_credential())
        assert await store.remove("cred-1") is True
        assert await store.get("cred-1") is None

    async def test_remove_not_found(self, store: InMemorySandboxCredentialStore) -> None:
        assert await store.remove("nope") is False
