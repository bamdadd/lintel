"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str]:
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url()
        # Strip SQLAlchemy dialect suffixes for raw asyncpg
        url = url.replace("postgresql+psycopg2://", "postgresql://")
        yield url
