"""Tests for sandbox pool API endpoints."""

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


# --- Image tests ---


class TestSandboxImages:
    def test_create_image(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-pool/images",
            json={"repository_url": "https://github.com/org/repo", "branch": "main"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repository_url"] == "https://github.com/org/repo"
        assert data["branch"] == "main"
        assert data["image_id"]

    def test_list_images(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/images",
            json={"repository_url": "https://github.com/org/a"},
        )
        client.post(
            "/api/v1/sandbox-pool/images",
            json={"repository_url": "https://github.com/org/b"},
        )
        resp = client.get("/api/v1/sandbox-pool/images")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_image(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/sandbox-pool/images",
            json={"repository_url": "https://github.com/org/repo"},
        ).json()
        resp = client.get(f"/api/v1/sandbox-pool/images/{created['image_id']}")
        assert resp.status_code == 200
        assert resp.json()["image_id"] == created["image_id"]

    def test_get_image_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/sandbox-pool/images/missing").status_code == 404

    def test_delete_image(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/sandbox-pool/images",
            json={"repository_url": "https://github.com/org/repo"},
        ).json()
        assert (
            client.delete(f"/api/v1/sandbox-pool/images/{created['image_id']}").status_code == 204
        )
        assert client.get(f"/api/v1/sandbox-pool/images/{created['image_id']}").status_code == 404

    def test_delete_image_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/sandbox-pool/images/missing").status_code == 404


# --- Pooled sandbox tests ---


def _seed_image(client: TestClient) -> str:
    return client.post(
        "/api/v1/sandbox-pool/images",
        json={"repository_url": "https://github.com/org/repo"},
    ).json()["image_id"]


def _seed_warm_sandbox(client: TestClient, project_id: str = "proj-1") -> dict:
    """Seed a warm sandbox via internal store helper by using the app directly."""
    import asyncio

    from lintel.sandbox_pool_api.routes import (
        _seed_warm_sandbox as _seed,
    )
    from lintel.sandbox_pool_api.routes import (
        pooled_sandbox_store_provider,
    )

    store = pooled_sandbox_store_provider.get()
    sb = asyncio.run(
        _seed(store, image_id="img-1", project_id=project_id),
    )
    from dataclasses import asdict

    return asdict(sb)


class TestPooledSandboxes:
    def test_list_sandboxes_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-pool/sandboxes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_acquire_sandbox_none_available(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-pool/sandboxes/acquire",
            json={"project_id": "proj-1", "pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 404

    def test_acquire_and_release_sandbox(self, client: TestClient) -> None:
        seeded = _seed_warm_sandbox(client, project_id="proj-acq")
        sandbox_id = seeded["sandbox_id"]

        # Acquire
        resp = client.post(
            "/api/v1/sandbox-pool/sandboxes/acquire",
            json={"project_id": "proj-acq", "pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_use"
        assert data["assigned_pipeline_run_id"] == "run-1"

        # Release
        resp = client.post(f"/api/v1/sandbox-pool/sandboxes/{sandbox_id}/release")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert resp.json()["assigned_pipeline_run_id"] == ""

    def test_release_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sandbox-pool/sandboxes/missing/release")
        assert resp.status_code == 404

    def test_list_sandboxes_filter_status(self, client: TestClient) -> None:
        _seed_warm_sandbox(client, project_id="proj-filt")
        resp = client.get("/api/v1/sandbox-pool/sandboxes", params={"status": "ready"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        for sb in resp.json():
            assert sb["status"] == "ready"


# --- Pool config tests ---


class TestPoolConfig:
    def test_get_config_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/sandbox-pool/config/proj-x").status_code == 404

    def test_put_and_get_config(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/sandbox-pool/config/proj-cfg",
            json={
                "min_warm": 3,
                "max_warm": 10,
                "ttl_seconds": 7200,
                "auto_rebuild_on_push": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-cfg"
        assert data["min_warm"] == 3
        assert data["max_warm"] == 10
        assert data["ttl_seconds"] == 7200
        assert data["auto_rebuild_on_push"] is False

        resp2 = client.get("/api/v1/sandbox-pool/config/proj-cfg")
        assert resp2.status_code == 200
        assert resp2.json()["project_id"] == "proj-cfg"

    def test_put_config_updates_existing(self, client: TestClient) -> None:
        client.put(
            "/api/v1/sandbox-pool/config/proj-upd",
            json={"min_warm": 1, "max_warm": 5, "ttl_seconds": 3600},
        )
        resp = client.put(
            "/api/v1/sandbox-pool/config/proj-upd",
            json={"min_warm": 4, "max_warm": 8, "ttl_seconds": 1800},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_warm"] == 4
        assert data["max_warm"] == 8

    def test_put_config_with_rebuild_interval(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/sandbox-pool/config/proj-rebuild",
            json={
                "min_warm": 2,
                "max_warm": 5,
                "ttl_seconds": 3600,
                "rebuild_interval_seconds": 900,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["rebuild_interval_seconds"] == 900


# --- Image rebuild tests ---


class TestImageRebuilds:
    def test_trigger_manual_rebuild(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-pool/images/rebuild",
            json={"project_id": "proj-rb", "commit_sha": "abc123", "branch": "main"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == "proj-rb"
        assert data["trigger"] == "manual"
        assert data["status"] == "completed"
        assert data["commit_sha"] == "abc123"
        assert data["image_id"]
        assert data["rebuild_id"]
        assert data["completed_at"] is not None

    def test_trigger_rebuild_creates_image(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-pool/images/rebuild",
            json={"project_id": "proj-rb2"},
        )
        assert resp.status_code == 201
        image_id = resp.json()["image_id"]

        img_resp = client.get(f"/api/v1/sandbox-pool/images/{image_id}")
        assert img_resp.status_code == 200
        assert img_resp.json()["image_id"] == image_id

    def test_list_rebuild_records_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-pool/images/rebuild-status")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_rebuild_records_after_rebuild(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/images/rebuild",
            json={"project_id": "proj-list"},
        )
        resp = client.get(
            "/api/v1/sandbox-pool/images/rebuild-status",
            params={"project_id": "proj-list"},
        )
        assert resp.status_code == 200
        records = resp.json()
        assert len(records) == 1
        assert records[0]["project_id"] == "proj-list"

    def test_list_rebuild_records_filter_status(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/images/rebuild",
            json={"project_id": "proj-filt"},
        )
        resp = client.get(
            "/api/v1/sandbox-pool/images/rebuild-status",
            params={"status": "completed"},
        )
        assert resp.status_code == 200
        for rec in resp.json():
            assert rec["status"] == "completed"

    def test_get_rebuild_record(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/sandbox-pool/images/rebuild",
            json={"project_id": "proj-get"},
        ).json()
        resp = client.get(
            f"/api/v1/sandbox-pool/images/rebuild-status/{created['rebuild_id']}",
        )
        assert resp.status_code == 200
        assert resp.json()["rebuild_id"] == created["rebuild_id"]

    def test_get_rebuild_record_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-pool/images/rebuild-status/missing")
        assert resp.status_code == 404
