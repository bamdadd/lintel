"""Tests for synchronous integration pattern scanning."""

from pathlib import Path

import pytest

from lintel.skills_api.integration_scanning import scan_sync_integrations


@pytest.mark.asyncio
async def test_detects_requests_get(sample_files: dict) -> None:
    results = await scan_sync_integrations([sample_files["http"]])
    matches = [r for r in results if r["target_service_hint"] == "requests"]
    assert len(matches) >= 1
    assert any("requests.get" in m["match_text"] for m in matches)
    assert all(m["protocol"] == "http" for m in matches)


@pytest.mark.asyncio
async def test_detects_httpx_client(sample_files: dict) -> None:
    results = await scan_sync_integrations([sample_files["http"]])
    matches = [r for r in results if r["target_service_hint"] == "httpx"]
    assert len(matches) >= 1
    assert any("httpx.AsyncClient" in m["match_text"] for m in matches)
    assert all(m["protocol"] == "http" for m in matches)


@pytest.mark.asyncio
async def test_detects_grpc_channel(sample_files: dict) -> None:
    results = await scan_sync_integrations([sample_files["http"]])
    matches = [r for r in results if r["target_service_hint"] == "grpc"]
    assert len(matches) >= 1
    assert all(m["protocol"] == "grpc" for m in matches)


@pytest.mark.asyncio
async def test_empty_files_returns_empty(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("")
    results = await scan_sync_integrations([str(empty_file)])
    assert results == []
