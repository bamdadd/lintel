"""Integration test: PII detection and vault round-trip."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import asyncpg
import pytest
from cryptography.fernet import Fernet
from lintel.contracts.events import ThreadMessageReceived
from lintel.contracts.types import ActorType, ThreadRef
from lintel.infrastructure.event_store.postgres import PostgresEventStore
from lintel.infrastructure.pii.presidio_firewall import PresidioFirewall
from lintel.infrastructure.vault.postgres_vault import PostgresPIIVault

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def pg_pool(postgres_url: str) -> AsyncGenerator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(postgres_url)
    assert pool is not None
    async with pool.acquire() as conn:
        with open("migrations/001_create_event_store.sql") as f:
            await conn.execute(f.read())
        with open("migrations/002_create_pii_vault.sql") as f:
            await conn.execute(f.read())
        await conn.execute("DELETE FROM events")
        await conn.execute("DELETE FROM pii_vault")
    yield pool
    await pool.close()


@pytest.fixture
def event_store(pg_pool: asyncpg.Pool) -> PostgresEventStore:
    return PostgresEventStore(pg_pool)


@pytest.fixture
def vault(pg_pool: asyncpg.Pool) -> PostgresPIIVault:
    key = Fernet.generate_key().decode()
    return PostgresPIIVault(pg_pool, encryption_key=key)


@pytest.fixture
def firewall(vault: PostgresPIIVault) -> PresidioFirewall:
    return PresidioFirewall(vault=vault, risk_threshold=1.1)


async def test_pii_detection_and_storage(
    firewall: PresidioFirewall,
    event_store: PostgresEventStore,
) -> None:
    """PII detected in message -> anonymized -> stored as event."""
    thread_ref = ThreadRef("W1", "C1", "pii.ts")

    result = await firewall.analyze_and_anonymize(
        "Please contact john@example.com for details",
        thread_ref,
    )

    assert not result.is_blocked
    assert "john@example.com" not in result.sanitized_text

    event = ThreadMessageReceived(
        actor_type=ActorType.HUMAN,
        actor_id="U123",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={"sanitized_text": result.sanitized_text, "sender_id": "U123"},
    )
    await event_store.append(thread_ref.stream_id, [event])

    stored = await event_store.read_stream(thread_ref.stream_id)
    assert len(stored) == 1
    assert "john@example.com" not in stored[0].payload["sanitized_text"]
