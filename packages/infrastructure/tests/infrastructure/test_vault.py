"""Tests for PostgresPIIVault with mocked asyncpg pool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from cryptography.fernet import Fernet
import pytest

from lintel.contracts.types import ThreadRef
from lintel.infrastructure.vault.postgres_vault import PostgresPIIVault

THREAD = ThreadRef("ws1", "ch1", "ts1")


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return pool, conn


class TestPostgresPIIVault:
    def setup_method(self) -> None:
        self.key = Fernet.generate_key().decode()
        self.pool, self.conn = _mock_pool()
        self.vault = PostgresPIIVault(self.pool, self.key)

    async def test_store_mapping_encrypts_value(self) -> None:
        await self.vault.store_mapping(THREAD, "<PERSON_1>", "PERSON", "John Doe")
        self.conn.execute.assert_called_once()
        call_args = self.conn.execute.call_args
        encrypted_bytes = call_args[0][4]
        fernet = Fernet(self.key.encode())
        decrypted = fernet.decrypt(encrypted_bytes).decode()
        assert decrypted == "John Doe"

    async def test_reveal_decrypts_value(self) -> None:
        fernet = Fernet(self.key.encode())
        encrypted = fernet.encrypt(b"secret@email.com")
        self.conn.fetchrow.return_value = {"encrypted_raw": encrypted}
        result = await self.vault.reveal(THREAD, "<EMAIL_1>", "admin-user")
        assert result == "secret@email.com"
        assert self.conn.execute.called

    async def test_reveal_missing_placeholder_raises(self) -> None:
        self.conn.fetchrow.return_value = None
        with pytest.raises(ValueError, match="No vault entry"):
            await self.vault.reveal(THREAD, "<MISSING>", "admin")

    def test_fernet_initialized_from_key(self) -> None:
        assert self.vault._fernet is not None

    async def test_store_uses_stream_id(self) -> None:
        await self.vault.store_mapping(THREAD, "<PH>", "TYPE", "value")
        call_args = self.conn.execute.call_args
        assert call_args[0][1] == THREAD.stream_id

    async def test_reveal_logs_audit(self) -> None:
        fernet = Fernet(self.key.encode())
        self.conn.fetchrow.return_value = {"encrypted_raw": fernet.encrypt(b"data")}
        await self.vault.reveal(THREAD, "<PH>", "revealer-123")
        update_call = self.conn.execute.call_args
        assert "revealer-123" in update_call[0]
