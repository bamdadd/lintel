"""Tests for the review score projection."""

from __future__ import annotations

from lintel.contracts.events import EventEnvelope
from lintel.projections.review_score_projection import ReviewScoreProjection


async def test_project_review_score() -> None:
    projection = ReviewScoreProjection()
    event = EventEnvelope(
        event_type="ReviewScoreRecorded",
        payload={
            "score_id": "s1",
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.5,
        },
    )
    await projection.project(event)

    scores = projection.get_latest_scores("repo-1")
    assert len(scores) == 1
    assert scores[0]["dimension"] == "security"
    assert scores[0]["latest_score"] == 7.5


async def test_project_multiple_dimensions() -> None:
    projection = ReviewScoreProjection()
    for dim in ["correctness", "security"]:
        event = EventEnvelope(
            event_type="ReviewScoreRecorded",
            payload={
                "score_id": f"s-{dim}",
                "repo_id": "repo-1",
                "dimension": dim,
                "score": 8.0,
            },
        )
        await projection.project(event)

    scores = projection.get_latest_scores("repo-1")
    assert len(scores) == 2


async def test_rebuild() -> None:
    projection = ReviewScoreProjection()
    events = [
        EventEnvelope(
            event_type="ReviewScoreRecorded",
            payload={"score_id": "s1", "repo_id": "r1", "dimension": "security", "score": 5.0},
        ),
        EventEnvelope(
            event_type="ReviewScoreRecorded",
            payload={"score_id": "s2", "repo_id": "r1", "dimension": "security", "score": 7.0},
        ),
    ]
    await projection.rebuild(events)
    scores = projection.get_latest_scores("r1")
    assert len(scores) == 1
    assert scores[0]["latest_score"] == 7.0
