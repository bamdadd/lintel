"""Tests for trust scores API endpoints (REQ-F029)."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_trust_score(
    client: TestClient,
    agent_id: str = "agent-1",
    score: int = 500,
    sponsor: str = "user-1",
) -> dict:
    resp = client.post(
        "/api/v1/trust-scores",
        json={"agent_id": agent_id, "score": score, "sponsor": sponsor},
    )
    assert resp.status_code == 201
    return resp.json()


class TestTrustScoreAPI:
    def test_create_trust_score(self, client: TestClient) -> None:
        data = _create_trust_score(client)
        assert data["agent_id"] == "agent-1"
        assert data["score"] == 500
        assert data["tier"] == "limited"
        assert data["sponsor"] == "user-1"

    def test_create_trust_score_high(self, client: TestClient) -> None:
        data = _create_trust_score(client, agent_id="agent-hi", score=950)
        assert data["tier"] == "full_autonomy"

    def test_create_trust_score_duplicate(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-dup")
        resp = client.post(
            "/api/v1/trust-scores",
            json={"agent_id": "agent-dup", "score": 500},
        )
        assert resp.status_code == 409

    def test_list_trust_scores(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-a")
        _create_trust_score(client, agent_id="agent-b")
        resp = client.get("/api/v1/trust-scores")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_trust_score(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-get")
        resp = client.get("/api/v1/trust-scores/agent-get")
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "agent-get"

    def test_get_trust_score_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/trust-scores/missing").status_code == 404

    def test_update_trust_score_sponsor(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-upd")
        resp = client.patch(
            "/api/v1/trust-scores/agent-upd",
            json={"sponsor": "new-sponsor"},
        )
        assert resp.status_code == 200
        assert resp.json()["sponsor"] == "new-sponsor"

    def test_update_trust_score_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/trust-scores/missing", json={"sponsor": "x"})
        assert resp.status_code == 404

    def test_adjust_trust_score_positive(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-adj", score=500)
        resp = client.post(
            "/api/v1/trust-scores/agent-adj/adjust",
            json={
                "kind": "task_success",
                "delta": 10,
                "reason": "Completed task successfully",
                "created_by": "system",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 510
        assert data["tier"] == "limited"

    def test_adjust_trust_score_negative(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-neg", score=350)
        resp = client.post(
            "/api/v1/trust-scores/agent-neg/adjust",
            json={
                "kind": "policy_violation",
                "delta": -100,
                "reason": "Violated security policy",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 250
        assert data["tier"] == "suspended"

    def test_adjust_trust_score_clamps_at_zero(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-clamp", score=50)
        resp = client.post(
            "/api/v1/trust-scores/agent-clamp/adjust",
            json={"delta": -200, "reason": "Major violation"},
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 0

    def test_adjust_trust_score_clamps_at_1000(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-max", score=990)
        resp = client.post(
            "/api/v1/trust-scores/agent-max/adjust",
            json={"delta": 50, "reason": "Bonus"},
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 1000

    def test_adjust_trust_score_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/trust-scores/missing/adjust",
            json={"delta": 10, "reason": "test"},
        )
        assert resp.status_code == 404

    def test_get_trust_history(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-hist", score=500)
        client.post(
            "/api/v1/trust-scores/agent-hist/adjust",
            json={"kind": "task_success", "delta": 10, "reason": "Good job"},
        )
        client.post(
            "/api/v1/trust-scores/agent-hist/adjust",
            json={"kind": "human_override", "delta": -20, "reason": "Correction"},
        )
        resp = client.get("/api/v1/trust-scores/agent-hist/history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2
        assert history[0]["score_before"] == 500
        assert history[0]["score_after"] == 510
        assert history[1]["score_before"] == 510
        assert history[1]["score_after"] == 490

    def test_get_trust_history_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/trust-scores/missing/history")
        assert resp.status_code == 404

    def test_delete_trust_score(self, client: TestClient) -> None:
        _create_trust_score(client, agent_id="agent-del")
        assert client.delete("/api/v1/trust-scores/agent-del").status_code == 204
        assert client.get("/api/v1/trust-scores/agent-del").status_code == 404

    def test_delete_trust_score_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/trust-scores/missing").status_code == 404

    def test_autonomy_tiers(self, client: TestClient) -> None:
        """Verify all autonomy tier thresholds."""
        cases = [
            ("tier-900", 900, "full_autonomy"),
            ("tier-700", 700, "normal"),
            ("tier-500", 500, "limited"),
            ("tier-300", 300, "approval_required"),
            ("tier-100", 100, "suspended"),
        ]
        for agent_id, score, expected_tier in cases:
            data = _create_trust_score(client, agent_id=agent_id, score=score)
            assert data["tier"] == expected_tier, f"score={score} expected {expected_tier}"
