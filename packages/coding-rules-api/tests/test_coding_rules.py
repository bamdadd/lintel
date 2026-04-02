"""Tests for coding rules API endpoints."""

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


def _create_rule(
    client: TestClient,
    name: str = "no-print",
    description: str = "Do not use print statements",
    content: str = "Avoid print() in production code. Use logging instead.",
    severity: str = "warning",
    scope: dict | None = None,
    active: bool = True,
    project_id: str = "",
) -> dict:
    resp = client.post(
        "/api/v1/coding-rules",
        json={
            "name": name,
            "description": description,
            "content": content,
            "severity": severity,
            "scope": scope or {"directory_pattern": "src/**", "file_pattern": "*.py"},
            "active": active,
            "project_id": project_id,
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestCodingRuleCRUD:
    def test_create_rule(self, client: TestClient) -> None:
        data = _create_rule(client)
        assert data["name"] == "no-print"
        assert data["severity"] == "warning"
        assert data["scope"]["directory_pattern"] == "src/**"
        assert data["scope"]["file_pattern"] == "*.py"
        assert data["active"] is True

    def test_list_rules(self, client: TestClient) -> None:
        _create_rule(client, name="rule-a")
        _create_rule(client, name="rule-b")
        resp = client.get("/api/v1/coding-rules")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        resp = client.get(f"/api/v1/coding-rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["rule_id"] == rule_id

    def test_get_rule_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/coding-rules/missing").status_code == 404

    def test_update_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        resp = client.patch(
            f"/api/v1/coding-rules/{rule_id}",
            json={"name": "updated-name", "severity": "error"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"
        assert resp.json()["severity"] == "error"

    def test_update_rule_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/coding-rules/missing", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        assert client.delete(f"/api/v1/coding-rules/{rule_id}").status_code == 204
        assert client.get(f"/api/v1/coding-rules/{rule_id}").status_code == 404

    def test_delete_rule_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/coding-rules/missing").status_code == 404


class TestCodingRuleMatch:
    def test_match_by_directory_pattern(self, client: TestClient) -> None:
        _create_rule(
            client,
            name="api-rule",
            scope={"directory_pattern": "src/api/**", "file_pattern": "*.py"},
        )
        resp = client.get("/api/v1/coding-rules/match", params={"path": "src/api/routes.py"})
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) >= 1
        assert rules[0]["name"] == "api-rule"

    def test_match_no_results(self, client: TestClient) -> None:
        _create_rule(
            client,
            name="api-only",
            scope={"directory_pattern": "src/api/**", "file_pattern": "*.py"},
        )
        resp = client.get("/api/v1/coding-rules/match", params={"path": "tests/test_foo.py"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_inactive_rule_not_matched(self, client: TestClient) -> None:
        _create_rule(
            client,
            name="inactive-rule",
            scope={"directory_pattern": "**", "file_pattern": "*"},
            active=False,
        )
        resp = client.get("/api/v1/coding-rules/match", params={"path": "any/file.py"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestViolations:
    def test_create_violation(self, client: TestClient) -> None:
        rule = _create_rule(client)
        resp = client.post(
            "/api/v1/coding-rules/violations",
            json={
                "rule_id": rule["rule_id"],
                "pipeline_run_id": "run-1",
                "file_path": "src/api/handler.py",
                "line_number": 42,
                "message": "print() used instead of logging",
                "agent_id": "agent-coder",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_id"] == rule["rule_id"]
        assert data["line_number"] == 42
        assert data["resolved"] is False

    def test_list_violations(self, client: TestClient) -> None:
        rule = _create_rule(client)
        client.post(
            "/api/v1/coding-rules/violations",
            json={"rule_id": rule["rule_id"], "message": "v1"},
        )
        client.post(
            "/api/v1/coding-rules/violations",
            json={"rule_id": rule["rule_id"], "message": "v2"},
        )
        resp = client.get("/api/v1/coding-rules/violations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_filter_violations_by_resolved(self, client: TestClient) -> None:
        rule = _create_rule(client)
        v_resp = client.post(
            "/api/v1/coding-rules/violations",
            json={"rule_id": rule["rule_id"], "message": "unresolved"},
        )
        vid = v_resp.json()["violation_id"]
        client.patch(f"/api/v1/coding-rules/violations/{vid}", json={"resolved": True})
        resp = client.get("/api/v1/coding-rules/violations", params={"resolved": False})
        assert resp.status_code == 200
        assert all(v["resolved"] is False for v in resp.json())

    def test_resolve_violation(self, client: TestClient) -> None:
        rule = _create_rule(client)
        v_resp = client.post(
            "/api/v1/coding-rules/violations",
            json={"rule_id": rule["rule_id"], "message": "bad"},
        )
        vid = v_resp.json()["violation_id"]
        resp = client.patch(
            f"/api/v1/coding-rules/violations/{vid}",
            json={"resolved": True},
        )
        assert resp.status_code == 200
        assert resp.json()["resolved"] is True

    def test_update_violation_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/coding-rules/violations/missing",
            json={"resolved": True},
        )
        assert resp.status_code == 404
