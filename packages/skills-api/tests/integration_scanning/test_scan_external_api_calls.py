"""Tests for external / third-party API call pattern scanning."""

import pytest

from lintel.skills_api.integration_scanning import scan_external_api_calls


@pytest.mark.asyncio
async def test_detects_stripe(sample_files: dict) -> None:
    results = await scan_external_api_calls([sample_files["external"]])
    matches = [r for r in results if r["service_name"] == "stripe"]
    assert len(matches) >= 1
    assert all(m["sdk_pattern"] == "sdk_import" for m in matches)


@pytest.mark.asyncio
async def test_detects_twilio(sample_files: dict) -> None:
    results = await scan_external_api_calls([sample_files["external"]])
    matches = [r for r in results if r["service_name"] == "twilio"]
    assert len(matches) >= 1
    assert any("twilio" in m["match_text"] for m in matches)


@pytest.mark.asyncio
async def test_detects_openai(sample_files: dict) -> None:
    results = await scan_external_api_calls([sample_files["external"]])
    matches = [r for r in results if r["service_name"] == "openai"]
    assert len(matches) >= 1
    assert any("openai" in m["match_text"] for m in matches)
