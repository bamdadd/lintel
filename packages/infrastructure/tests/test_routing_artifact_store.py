"""Tests for RoutingArtifactStore size-threshold routing logic."""

from __future__ import annotations

from lintel.contracts.protocols.artifact_store import ArtifactRef


class StubPostgresArtifactStore:
    """Stub that records calls and tracks backend metadata."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}
        self._backends: dict[str, str] = {}
        self._refs: dict[str, ArtifactRef] = {}

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        self._content[artifact_id] = content
        self._backends[artifact_id] = "postgres"
        self._refs[artifact_id] = ArtifactRef(
            artifact_id=artifact_id,
            storage_backend="postgres",
            location=artifact_id,
            size_bytes=len(content),
            content_type=str(metadata.get("content_type", "application/octet-stream")),
            pipeline_run_id=str(metadata.get("pipeline_run_id", "")),
        )
        return artifact_id

    async def retrieve(self, artifact_id: str) -> bytes:
        return self._content[artifact_id]

    async def get_backend(self, artifact_id: str) -> str:
        return self._backends.get(artifact_id, "postgres")

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        return [r for r in self._refs.values() if r.pipeline_run_id == pipeline_run_id]


class StubObjectStore:
    """Stub for the S3/object store side."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        self._content[artifact_id] = content
        return f"s3://bucket/artifacts/{artifact_id}"

    async def retrieve(self, artifact_id: str) -> bytes:
        return self._content[artifact_id]

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        return []


async def test_small_content_routes_to_postgres() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=100)  # type: ignore[arg-type]

    location = await router.store("a1", b"small", {"pipeline_run_id": "r1"})
    assert location == "a1"
    assert "a1" in pg._content
    assert "a1" not in obj._content


async def test_large_content_routes_to_object_store() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=10)  # type: ignore[arg-type]

    content = b"x" * 50
    location = await router.store("a1", content, {"pipeline_run_id": "r1"})
    assert "s3://" in location
    assert "a1" in obj._content
    assert "a1" not in pg._content


async def test_retrieve_delegates_based_on_backend() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=100)  # type: ignore[arg-type]

    # Store small content (goes to postgres)
    await router.store("a1", b"pg-data", {"pipeline_run_id": "r1"})
    result = await router.retrieve("a1")
    assert result == b"pg-data"


async def test_retrieve_s3_backend() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=100)  # type: ignore[arg-type]

    # Simulate an artifact stored in s3
    obj._content["a2"] = b"s3-data"
    pg._backends["a2"] = "s3"

    result = await router.retrieve("a2")
    assert result == b"s3-data"


async def test_list_refs_delegates_to_postgres() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=100)  # type: ignore[arg-type]

    await router.store("a1", b"data", {"pipeline_run_id": "r1"})
    refs = await router.list_refs("r1")
    assert len(refs) == 1
    assert refs[0].artifact_id == "a1"


async def test_exact_threshold_routes_to_postgres() -> None:
    from lintel.infrastructure.stores.routing_artifact_store import RoutingArtifactStore

    pg = StubPostgresArtifactStore()
    obj = StubObjectStore()
    router = RoutingArtifactStore(pg, obj, size_threshold_bytes=10)  # type: ignore[arg-type]

    # Exactly at threshold — should go to postgres (only > threshold goes to s3)
    content = b"x" * 10
    await router.store("a1", content, {})
    assert "a1" in pg._content
    assert "a1" not in obj._content
