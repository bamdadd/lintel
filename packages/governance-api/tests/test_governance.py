"""Tests for governance API endpoints (policies, audit)."""

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


def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


# ======================== GOVERNANCE POLICIES ========================


class TestGovernancePoliciesAPI:
    def test_create_governance_policy(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/governance/policies",
            json={
                "policy_id": "gov-1",
                "project_id": "proj-1",
                "name": "No sandbox exec for reviewer",
                "scope": "sandbox_exec",
                "agent_roles": ["reviewer"],
                "default_decision": "deny",
                "rate_limit": 10,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "No sandbox exec for reviewer"
        assert data["scope"] == "sandbox_exec"
        assert data["default_decision"] == "deny"
        assert data["agent_roles"] == ["reviewer"]

    def test_create_duplicate_policy_returns_409(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-dup", "project_id": "proj-1", "name": "Dup"},
        )
        resp = client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-dup", "project_id": "proj-1", "name": "Dup"},
        )
        assert resp.status_code == 409

    def test_list_governance_policies(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-l1", "project_id": "proj-1", "name": "P1"},
        )
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-l2", "project_id": "proj-1", "name": "P2"},
        )
        resp = client.get("/api/v1/governance/policies", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_governance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-g1", "project_id": "proj-1", "name": "Get Me"},
        )
        resp = client.get("/api/v1/governance/policies/gov-g1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_get_nonexistent_policy_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/governance/policies/nonexistent")
        assert resp.status_code == 404

    def test_update_governance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-u1", "project_id": "proj-1", "name": "Update Me"},
        )
        resp = client.patch(
            "/api/v1/governance/policies/gov-u1",
            json={"default_decision": "require_approval", "rate_limit": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["default_decision"] == "require_approval"
        assert resp.json()["rate_limit"] == 5

    def test_update_nonexistent_policy_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/governance/policies/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_governance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/policies",
            json={"policy_id": "gov-d1", "project_id": "proj-1", "name": "Delete Me"},
        )
        assert client.delete("/api/v1/governance/policies/gov-d1").status_code == 204

    def test_delete_nonexistent_policy_returns_404(self, client: TestClient) -> None:
        assert client.delete("/api/v1/governance/policies/nonexistent").status_code == 404


# ======================== GOVERNANCE AUDIT ========================


class TestGovernanceAuditAPI:
    def test_record_governance_audit(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/governance/audit",
            json={
                "entry_id": "aud-1",
                "project_id": "proj-1",
                "policy_id": "gov-1",
                "agent_id": "agent-coder",
                "agent_role": "coder",
                "action": "sandbox_write_file",
                "decision": "allow",
                "trust_score": 0.85,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "allow"
        assert data["trust_score"] == 0.85

    def test_record_deny_audit(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/governance/audit",
            json={
                "entry_id": "aud-2",
                "project_id": "proj-1",
                "agent_id": "agent-reviewer",
                "action": "execute_command",
                "decision": "deny",
                "reason": "Reviewer not allowed to execute commands",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["decision"] == "deny"

    def test_list_governance_audit(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/audit",
            json={"entry_id": "aud-l1", "project_id": "proj-1", "decision": "allow"},
        )
        resp = client.get("/api/v1/governance/audit", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_governance_audit(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/governance/audit",
            json={"entry_id": "aud-g1", "project_id": "proj-1"},
        )
        resp = client.get("/api/v1/governance/audit/aud-g1")
        assert resp.status_code == 200

    def test_get_nonexistent_audit_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/governance/audit/nonexistent")
        assert resp.status_code == 404
