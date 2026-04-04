"""Tests for cloud environments API."""

from fastapi.testclient import TestClient


def _provision(
    client: TestClient,
    cloud_environment_id: str = "ce1",
    provider: str = "aws_ec2",
) -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/cloud-environments/provision",
        json={
            "cloud_environment_id": cloud_environment_id,
            "name": "Test VM",
            "provider": provider,
        },
    ).json()


class TestProvision:
    def test_provision_aws(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cloud-environments/provision",
            json={
                "cloud_environment_id": "ce1",
                "name": "Dev VM",
                "provider": "aws_ec2",
                "instance_type": "t3.large",
                "region": "eu-west-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cloud_environment_id"] == "ce1"
        assert data["provider"] == "aws_ec2"
        assert data["instance_type"] == "t3.large"
        assert data["region"] == "eu-west-1"
        assert data["status"] == "provisioning"

    def test_provision_gcp(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cloud-environments/provision",
            json={
                "cloud_environment_id": "ce2",
                "name": "GCP VM",
                "provider": "gcp_ce",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["provider"] == "gcp_ce"

    def test_provision_duplicate_returns_409(self, client: TestClient) -> None:
        _provision(client, "dup")
        resp = client.post(
            "/api/v1/cloud-environments/provision",
            json={"cloud_environment_id": "dup", "name": "Again", "provider": "aws_ec2"},
        )
        assert resp.status_code == 409


class TestDestroy:
    def test_destroy_environment(self, client: TestClient) -> None:
        _provision(client, "ce1")
        resp = client.post(
            "/api/v1/cloud-environments/ce1/destroy",
            json={"force": False},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "destroying"

    def test_destroy_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/cloud-environments/missing/destroy",
            json={},
        )
        assert resp.status_code == 404


class TestListAndGet:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cloud-environments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_items(self, client: TestClient) -> None:
        _provision(client, "a")
        _provision(client, "b")
        resp = client.get("/api/v1/cloud-environments")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_by_id(self, client: TestClient) -> None:
        _provision(client, "ce1")
        resp = client.get("/api/v1/cloud-environments/ce1")
        assert resp.status_code == 200
        assert resp.json()["cloud_environment_id"] == "ce1"

    def test_get_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cloud-environments/missing")
        assert resp.status_code == 404
