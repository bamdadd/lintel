"""Tests for workflow ACL API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestAclRulesCRUD:
    def test_list_rules_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflow-acl/rules")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_rule(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1", "effect": "deny"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["connection_id"] == "conn-1"
        assert data["effect"] == "deny"
        assert "rule_id" in data

    def test_create_rule_with_workflow_types(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflow-acl/rules",
            json={
                "connection_id": "conn-2",
                "workflow_types": ["feature_to_pr"],
                "project_id": "proj-1",
                "effect": "allow",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["workflow_types"] == ["feature_to_pr"]
        assert data["project_id"] == "proj-1"
        assert data["effect"] == "allow"

    def test_list_rules_after_create(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1"},
        )
        client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-2"},
        )
        resp = client.get("/api/v1/workflow-acl/rules")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_rule(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1"},
        ).json()
        rule_id = created["rule_id"]
        resp = client.delete(f"/api/v1/workflow-acl/rules/{rule_id}")
        assert resp.status_code == 204
        assert client.get("/api/v1/workflow-acl/rules").json() == []

    def test_delete_rule_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/workflow-acl/rules/nonexistent")
        assert resp.status_code == 404


class TestAclCheck:
    def test_check_no_rules_allows(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-1", "workflow_type": "feature_to_pr"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["reason"] == "no_matching_rules"

    def test_check_deny_rule_blocks(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1", "effect": "deny"},
        )
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-1", "workflow_type": "feature_to_pr"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert "denied_by_rule" in data["reason"]

    def test_check_allow_rule_permits(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1", "effect": "allow"},
        )
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-1", "workflow_type": "feature_to_pr"},
        )
        assert resp.status_code == 200
        assert resp.json()["allowed"] is True

    def test_check_scoped_to_workflow_type(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-acl/rules",
            json={
                "connection_id": "conn-1",
                "workflow_types": ["bugfix"],
                "effect": "deny",
            },
        )
        # Different workflow type — rule doesn't match
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-1", "workflow_type": "feature_to_pr"},
        )
        assert resp.json()["allowed"] is True

        # Matching workflow type — denied
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-1", "workflow_type": "bugfix"},
        )
        assert resp.json()["allowed"] is False

    def test_check_different_connection_not_affected(self, client: TestClient) -> None:
        client.post(
            "/api/v1/workflow-acl/rules",
            json={"connection_id": "conn-1", "effect": "deny"},
        )
        resp = client.post(
            "/api/v1/workflow-acl/check",
            json={"connection_id": "conn-other", "workflow_type": "feature_to_pr"},
        )
        assert resp.json()["allowed"] is True
