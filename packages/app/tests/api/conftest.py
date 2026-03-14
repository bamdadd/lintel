"""Shared fixtures for API tests supporting both storage backends."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_memory_client() -> Generator[TestClient]:
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)


def _make_postgres_client(postgres_url: str) -> Generator[TestClient]:
    import asyncio

    import asyncpg

    os.environ["LINTEL_STORAGE_BACKEND"] = "postgres"
    os.environ["LINTEL_DB_DSN"] = postgres_url

    # Run migrations before starting the app
    async def _migrate() -> None:
        pool = await asyncpg.create_pool(postgres_url)
        assert pool is not None
        async with pool.acquire() as conn:
            for migration in sorted(
                f.name
                for f in __import__("pathlib").Path("migrations").iterdir()
                if f.suffix == ".sql"
            ):
                with open(f"migrations/{migration}") as f:
                    await conn.execute(f.read())
            # Clean all entity data between tests
            await conn.execute("DELETE FROM entities")
            await conn.execute("DELETE FROM events")
        await pool.close()

    asyncio.get_event_loop().run_until_complete(_migrate())

    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)
    os.environ.pop("LINTEL_DB_DSN", None)


@pytest.fixture(params=["memory", "postgres"])
def client(request: pytest.FixtureRequest) -> Generator[TestClient]:
    """Parametrized client that runs each test against both backends."""
    if request.param == "postgres":
        if not request.config.getoption("--run-postgres", default=False):
            pytest.skip("postgres tests disabled (use --run-postgres)")
        postgres_url = request.getfixturevalue("postgres_url")
        yield from _make_postgres_client(postgres_url)
    else:
        yield from _make_memory_client()
