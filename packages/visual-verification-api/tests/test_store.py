"""Tests for InMemoryVisualVerificationStore."""

from lintel.visual_verification_api.store import InMemoryVisualVerificationStore
from lintel.visual_verification_api.types import VerificationStatus, VisualVerification


class TestInMemoryVisualVerificationStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryVisualVerificationStore()
        v = VisualVerification(id="vv-1", pipeline_run_id="run-1", stage_name="implement")
        result = await store.add(v)
        assert result["id"] == "vv-1"
        fetched = await store.get("vv-1")
        assert fetched is not None
        assert fetched["stage_name"] == "implement"

    async def test_get_returns_none(self) -> None:
        store = InMemoryVisualVerificationStore()
        assert await store.get("missing") is None

    async def test_list_all(self) -> None:
        store = InMemoryVisualVerificationStore()
        await store.add(VisualVerification(id="a", pipeline_run_id="r1", stage_name="s1"))
        await store.add(VisualVerification(id="b", pipeline_run_id="r2", stage_name="s2"))
        assert len(await store.list_all()) == 2

    async def test_list_by_pipeline(self) -> None:
        store = InMemoryVisualVerificationStore()
        await store.add(VisualVerification(id="a", pipeline_run_id="r1", stage_name="s1"))
        await store.add(VisualVerification(id="b", pipeline_run_id="r2", stage_name="s2"))
        result = await store.list_by_pipeline("r1")
        assert len(result) == 1
        assert result[0]["pipeline_run_id"] == "r1"

    async def test_update(self) -> None:
        store = InMemoryVisualVerificationStore()
        await store.add(VisualVerification(id="vv-1", pipeline_run_id="run-1", stage_name="impl"))
        result = await store.update("vv-1", {"status": VerificationStatus.APPROVED})
        assert result is not None
        assert result["status"] == "approved"

    async def test_update_returns_none_for_missing(self) -> None:
        store = InMemoryVisualVerificationStore()
        assert await store.update("missing", {"status": "approved"}) is None

    async def test_remove(self) -> None:
        store = InMemoryVisualVerificationStore()
        await store.add(VisualVerification(id="vv-1", pipeline_run_id="run-1", stage_name="impl"))
        assert await store.remove("vv-1") is True
        assert await store.get("vv-1") is None

    async def test_remove_missing(self) -> None:
        store = InMemoryVisualVerificationStore()
        assert await store.remove("missing") is False
