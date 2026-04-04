"""Tests for kernel-policy API."""

from fastapi.testclient import TestClient


class TestKernelPolicyAPI:
    def test_create_kernel_policy_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/kernel-policies",
            json={
                "policy_id": "kp-1",
                "name": "Seccomp Sandbox",
                "policy_type": "seccomp",
                "description": "Restrict syscalls",
                "rules": {"default_action": "deny"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "kp-1"
        assert data["name"] == "Seccomp Sandbox"
        assert data["policy_type"] == "seccomp"
        assert data["status"] == "draft"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-dup", "name": "P1", "policy_type": "seccomp"},
        )
        resp = client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-dup", "name": "P2", "policy_type": "apparmor"},
        )
        assert resp.status_code == 409

    def test_list_kernel_policies_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/kernel-policies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_kernel_policies(self, client: TestClient) -> None:
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-a", "name": "A", "policy_type": "seccomp"},
        )
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-b", "name": "B", "policy_type": "apparmor"},
        )
        resp = client.get("/api/v1/kernel-policies")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_kernel_policy_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-2", "name": "AppArmor Profile", "policy_type": "apparmor"},
        )
        resp = client.get("/api/v1/kernel-policies/kp-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "AppArmor Profile"

    def test_get_kernel_policy_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/kernel-policies/nonexistent")
        assert resp.status_code == 404

    def test_delete_kernel_policy_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-3", "name": "To Delete", "policy_type": "seccomp"},
        )
        resp = client.delete("/api/v1/kernel-policies/kp-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/kernel-policies/kp-3").status_code == 404

    def test_delete_kernel_policy_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/kernel-policies/nonexistent")
        assert resp.status_code == 404

    def test_apply_policy_to_sandbox(self, client: TestClient) -> None:
        client.post(
            "/api/v1/kernel-policies",
            json={"policy_id": "kp-4", "name": "Apply Me", "policy_type": "seccomp"},
        )
        resp = client.post(
            "/api/v1/kernel-policies/apply/sandbox-1",
            json={"policy_id": "kp-4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_id"] == "sandbox-1"
        assert data["policy_id"] == "kp-4"
        assert data["status"] == "applied"
        # Verify policy status updated
        policy = client.get("/api/v1/kernel-policies/kp-4").json()
        assert policy["status"] == "applied"

    def test_apply_policy_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/kernel-policies/apply/sandbox-1",
            json={"policy_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_apply_policy_missing_policy_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/kernel-policies/apply/sandbox-1",
            json={},
        )
        assert resp.status_code == 422
