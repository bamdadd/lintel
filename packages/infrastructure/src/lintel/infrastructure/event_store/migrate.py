"""Simple migration runner for event store schema."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg


async def run_migrations(dsn: str | None = None) -> None:
    """Run all SQL migrations in order."""
    dsn = dsn or os.environ.get(
        "LINTEL_DB_DSN",
        os.environ.get("DATABASE_URL", "postgresql://lintel:lintel@localhost:5432/lintel"),
    )
    conn = await asyncpg.connect(dsn)
    try:
        # Walk up to find the repo root (contains migrations/ and pyproject.toml)
        p = Path(__file__).resolve()
        while p != p.parent:
            if (p / "migrations").is_dir() and (p / "pyproject.toml").is_file():
                break
            p = p.parent
        migrations_dir = p / "migrations"
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            sql = sql_file.read_text()
            await conn.execute(sql)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
