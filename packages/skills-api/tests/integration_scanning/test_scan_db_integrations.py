"""Tests for database client integration pattern scanning."""

import pytest

from lintel.skills_api.integration_scanning import scan_db_integrations


@pytest.mark.asyncio
async def test_detects_sqlalchemy_engine(sample_files: dict) -> None:
    results = await scan_db_integrations([sample_files["db"]])
    matches = [r for r in results if r["db_type"] == "sqlalchemy"]
    assert len(matches) >= 1
    assert any(m["client_pattern"] == "create_engine" for m in matches)


@pytest.mark.asyncio
async def test_detects_asyncpg_pool(sample_files: dict) -> None:
    results = await scan_db_integrations([sample_files["db"]])
    matches = [r for r in results if r["db_type"] == "asyncpg"]
    assert len(matches) >= 1
    assert any(m["client_pattern"] in ("create_pool", "import") for m in matches)


@pytest.mark.asyncio
async def test_detects_pymongo_client(sample_files: dict) -> None:
    results = await scan_db_integrations([sample_files["db"]])
    matches = [r for r in results if r["db_type"] == "mongodb"]
    assert len(matches) >= 1
    assert any(m["client_pattern"] == "MongoClient" for m in matches)
