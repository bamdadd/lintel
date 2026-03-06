"""Encrypted PII vault. Human-only reveal with audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from cryptography.fernet import Fernet

if TYPE_CHECKING:
    import asyncpg

    from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()


class PostgresPIIVault:
    """Implements PIIVault protocol with Postgres + Fernet encryption."""

    def __init__(self, pool: asyncpg.Pool, encryption_key: str) -> None:
        self._pool = pool
        self._fernet = Fernet(encryption_key.encode())

    async def store_mapping(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        entity_type: str,
        raw_value: str,
    ) -> None:
        encrypted = self._fernet.encrypt(raw_value.encode())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pii_vault
                    (thread_ref, placeholder, entity_type, encrypted_raw)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (thread_ref, placeholder) DO NOTHING
                """,
                thread_ref.stream_id,
                placeholder,
                entity_type,
                encrypted,
            )

    async def reveal(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        revealer_id: str,
    ) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT encrypted_raw FROM pii_vault "
                "WHERE thread_ref = $1 AND placeholder = $2",
                thread_ref.stream_id,
                placeholder,
            )
            if not row:
                msg = f"No vault entry for {placeholder}"
                raise ValueError(msg)

            await conn.execute(
                "UPDATE pii_vault SET revealed_at = now(), revealed_by = $1 "
                "WHERE thread_ref = $2 AND placeholder = $3",
                revealer_id,
                thread_ref.stream_id,
                placeholder,
            )

        logger.warning(
            "pii_revealed",
            thread_ref=str(thread_ref),
            placeholder=placeholder,
            revealer_id=revealer_id,
        )
        return self._fernet.decrypt(row["encrypted_raw"]).decode()
