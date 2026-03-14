"""Tests for event store migration runner (mocked asyncpg)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, patch

from lintel.event_store.migrate import run_migrations


class TestRunMigrations:
    async def test_uses_dsn_from_parameter(self) -> None:
        with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            mock_conn.close = AsyncMock()

            # Will fail because migrations dir may not exist, but we verify connect call
            with contextlib.suppress(FileNotFoundError, StopIteration):
                await run_migrations("postgresql://test:test@localhost/test")

            mock_connect.assert_called_once_with("postgresql://test:test@localhost/test")
