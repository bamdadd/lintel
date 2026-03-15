"""Tests for file and blob storage integration pattern scanning."""

import pytest

from lintel.skills_api.integration_scanning import scan_file_blob_integrations


@pytest.mark.asyncio
async def test_detects_boto3_s3(sample_files: dict) -> None:
    results = await scan_file_blob_integrations([sample_files["blob"]])
    matches = [r for r in results if r["storage_type"] == "s3"]
    assert len(matches) >= 1
    assert any(m["operation"] in ("client", "import") for m in matches)


@pytest.mark.asyncio
async def test_detects_azure_blob(sample_files: dict) -> None:
    results = await scan_file_blob_integrations([sample_files["blob"]])
    matches = [r for r in results if r["storage_type"] == "azure_blob"]
    assert len(matches) >= 1
    assert any(m["operation"] in ("import", "BlobServiceClient") for m in matches)
