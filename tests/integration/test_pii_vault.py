"""Integration tests for Postgres PII vault."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg
from cryptography.fernet import Fernet
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.vault.postgres_vault import PostgresPIIVault
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def vault(postgres_url: str) -> AsyncGenerator[PostgresPIIVault]:
    pool = await asyncpg.create_pool(postgres_url)
    assert pool is not None
    async with pool.acquire() as conn:
        with open("migrations/002_create_pii_vault.sql") as f:
            await conn.execute(f.read())
        await conn.execute("DELETE FROM pii_vault")
    key = Fernet.generate_key().decode()
    v = PostgresPIIVault(pool, key)
    yield v
    await pool.close()


@pytest.fixture
def thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1234.5678")


async def test_store_and_reveal(vault: PostgresPIIVault, thread_ref: ThreadRef) -> None:
    await vault.store_mapping(
        thread_ref=thread_ref,
        placeholder="<PERSON_1>",
        entity_type="PERSON",
        raw_value="John Doe",
    )
    revealed = await vault.reveal(thread_ref, "<PERSON_1>", revealer_id="admin-user")
    assert revealed == "John Doe"


async def test_reveal_nonexistent_raises(vault: PostgresPIIVault, thread_ref: ThreadRef) -> None:
    with pytest.raises(ValueError, match="No vault entry"):
        await vault.reveal(thread_ref, "<MISSING_1>", revealer_id="admin")


async def test_store_idempotent(vault: PostgresPIIVault, thread_ref: ThreadRef) -> None:
    await vault.store_mapping(
        thread_ref=thread_ref,
        placeholder="<EMAIL_1>",
        entity_type="EMAIL_ADDRESS",
        raw_value="test@example.com",
    )
    # Storing again should not raise
    await vault.store_mapping(
        thread_ref=thread_ref,
        placeholder="<EMAIL_1>",
        entity_type="EMAIL_ADDRESS",
        raw_value="test@example.com",
    )
    revealed = await vault.reveal(thread_ref, "<EMAIL_1>", revealer_id="admin")
    assert revealed == "test@example.com"


async def test_reveal_records_audit(vault: PostgresPIIVault, thread_ref: ThreadRef) -> None:
    await vault.store_mapping(
        thread_ref=thread_ref,
        placeholder="<PERSON_1>",
        entity_type="PERSON",
        raw_value="Jane Smith",
    )
    await vault.reveal(thread_ref, "<PERSON_1>", revealer_id="audit-user")

    # Verify audit fields were set
    async with vault._pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT revealed_at, revealed_by FROM pii_vault "
            "WHERE thread_ref = $1 AND placeholder = $2",
            thread_ref.stream_id,
            "<PERSON_1>",
        )
    assert row is not None
    assert row["revealed_at"] is not None
    assert row["revealed_by"] == "audit-user"
