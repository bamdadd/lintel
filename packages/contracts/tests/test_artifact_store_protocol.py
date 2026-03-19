"""Tests for the ArtifactStore Protocol and a local fake implementation."""

from __future__ import annotations

import pytest

from lintel.contracts.protocols.artifact_store import ArtifactRef, ArtifactStore


class FakeArtifactStore:
    """In-memory ArtifactStore for tests."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}
        self._refs: dict[str, ArtifactRef] = {}

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        location = f"mem://{artifact_id}"
        self._content[artifact_id] = content
        self._refs[artifact_id] = ArtifactRef(
            artifact_id=artifact_id,
            storage_backend="postgres",
            location=location,
            size_bytes=len(content),
            content_type=str(metadata.get("content_type", "application/octet-stream")),
            pipeline_run_id=str(metadata.get("pipeline_run_id", "")),
        )
        return location

    async def retrieve(self, artifact_id: str) -> bytes:
        if artifact_id not in self._content:
            msg = f"Artifact {artifact_id} not found"
            raise KeyError(msg)
        return self._content[artifact_id]

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        return [ref for ref in self._refs.values() if ref.pipeline_run_id == pipeline_run_id]


def test_fake_artifact_store_satisfies_protocol() -> None:
    """FakeArtifactStore is structurally compatible with ArtifactStore."""
    store = FakeArtifactStore()
    assert isinstance(store, ArtifactStore)


async def test_store_and_retrieve() -> None:
    store = FakeArtifactStore()
    content = b"hello world"
    metadata: dict[str, object] = {"content_type": "text/plain", "pipeline_run_id": "run-1"}

    location = await store.store("art-1", content, metadata)
    assert location == "mem://art-1"

    retrieved = await store.retrieve("art-1")
    assert retrieved == content


async def test_retrieve_missing_raises() -> None:
    store = FakeArtifactStore()
    with pytest.raises(KeyError, match="art-missing"):
        await store.retrieve("art-missing")


async def test_list_refs_filters_by_pipeline_run() -> None:
    store = FakeArtifactStore()
    await store.store("a1", b"x", {"pipeline_run_id": "run-1"})
    await store.store("a2", b"y", {"pipeline_run_id": "run-2"})
    await store.store("a3", b"z", {"pipeline_run_id": "run-1"})

    refs = await store.list_refs("run-1")
    assert len(refs) == 2
    assert {r.artifact_id for r in refs} == {"a1", "a3"}

    refs_2 = await store.list_refs("run-2")
    assert len(refs_2) == 1
    assert refs_2[0].artifact_id == "a2"


async def test_list_refs_empty() -> None:
    store = FakeArtifactStore()
    refs = await store.list_refs("nonexistent")
    assert refs == []


async def test_artifact_ref_fields() -> None:
    store = FakeArtifactStore()
    await store.store("a1", b"data", {"content_type": "application/json", "pipeline_run_id": "r1"})

    refs = await store.list_refs("r1")
    assert len(refs) == 1
    ref = refs[0]
    assert ref.artifact_id == "a1"
    assert ref.storage_backend == "postgres"
    assert ref.size_bytes == 4
    assert ref.content_type == "application/json"
    assert ref.pipeline_run_id == "r1"
