"""Tests for CorrectionProjection."""

from __future__ import annotations

from lintel.contracts.events import EventEnvelope
from lintel.projections.correction_projection import CorrectionProjection


class TestCorrectionProjection:
    async def test_on_agent_corrected(self) -> None:
        proj = CorrectionProjection()
        await proj.handle(
            EventEnvelope(
                event_type="AgentCorrected",
                payload={
                    "approval_id": "ap-1",
                    "run_id": "run-1",
                    "stage": "review",
                    "original_output": {"summary": "old"},
                    "correction": {"summary": "new"},
                    "reasoning": "summary was wrong",
                    "corrected_by": "user1",
                },
            )
        )
        all_corrections = proj.get_all()
        assert len(all_corrections) == 1
        assert all_corrections[0]["correction"] == {"summary": "new"}

    async def test_get_by_run_id(self) -> None:
        proj = CorrectionProjection()
        await proj.handle(
            EventEnvelope(
                event_type="AgentCorrected",
                payload={
                    "approval_id": "a1",
                    "run_id": "r1",
                    "stage": "s1",
                },
            )
        )
        await proj.handle(
            EventEnvelope(
                event_type="AgentCorrected",
                payload={
                    "approval_id": "a2",
                    "run_id": "r2",
                    "stage": "s2",
                },
            )
        )
        results = proj.get_by_run_id("r1")
        assert len(results) == 1
        assert results[0]["approval_id"] == "a1"
