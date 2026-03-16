"""In-memory fake implementation of ArtifactStore for use in tests."""

from __future__ import annotations

from lintel.contracts.protocols.artifact_store import ArtifactRef


class FakeArtifactStore:
    """ArtifactStore implementation backed by an in-memory dict.

    Satisfies the ``ArtifactStore`` Protocol structurally so it can be used
    as a drop-in replacement in tests.
    """

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
