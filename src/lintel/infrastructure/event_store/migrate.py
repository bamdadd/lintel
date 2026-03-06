"""Simple migration runner for event store schema."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg


async def run_migrations(dsn: str | None = None) -> None:
    """Run all SQL migrations in order."""
    dsn = dsn or os.environ.get("DATABASE_URL", "postgresql://localhost:5432/lintel")
    conn = await asyncpg.connect(dsn)
    try:
        migrations_dir = Path(__file__).resolve().parents[4] / "migrations"
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            sql = sql_file.read_text()
            await conn.execute(sql)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
