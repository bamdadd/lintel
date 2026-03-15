"""Tests for asynchronous / message-broker integration pattern scanning."""

import pytest

from lintel.skills_api.integration_scanning import scan_async_integrations


@pytest.mark.asyncio
async def test_detects_kafka_producer(sample_files: dict) -> None:
    results = await scan_async_integrations([sample_files["async"]])
    matches = [
        r for r in results if r["pattern_type"] == "kafka" and "KafkaProducer" in r["match_text"]
    ]
    assert len(matches) >= 1
    assert all(m["protocol"] == "kafka" for m in matches)


@pytest.mark.asyncio
async def test_detects_kafka_consumer(sample_files: dict) -> None:
    results = await scan_async_integrations([sample_files["async"]])
    matches = [
        r for r in results if r["pattern_type"] == "kafka" and "KafkaConsumer" in r["match_text"]
    ]
    assert len(matches) >= 1
    assert all(m["protocol"] == "kafka" for m in matches)


@pytest.mark.asyncio
async def test_detects_nats_connect(sample_files: dict) -> None:
    results = await scan_async_integrations([sample_files["async"]])
    matches = [r for r in results if r["pattern_type"] == "nats"]
    assert len(matches) >= 1
    assert any(
        "nats.connect" in m["match_text"] or "import nats" in m["match_text"] for m in matches
    )
