"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import Generator


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-postgres",
        action="store_true",
        default=False,
        help="Run tests against a Postgres backend (starts testcontainer)",
    )


@pytest.fixture(scope="session")
def postgres_url(request: pytest.FixtureRequest) -> Generator[str]:
    if not request.config.getoption("--run-postgres"):
        pytest.skip("postgres tests disabled (use --run-postgres)")
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url()
        # Strip SQLAlchemy dialect suffixes for raw asyncpg
        url = url.replace("postgresql+psycopg2://", "postgresql://")
        yield url
