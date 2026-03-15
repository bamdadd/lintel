"""Tests for project selection flow in chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestProjectSelectionInChat:
    """When a workflow is triggered but no project is set, chat should prompt."""

    def test_workflow_trigger_without_project_prompts_selection(self, client: TestClient) -> None:
        """A workflow-triggering message without project_id should prompt for project."""
        # Create a project first
        client.post("/api/v1/projects", json={"name": "My Project", "project_id": "proj-1"})

        # Create conversation without project_id, with a workflow-triggering message
        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        # Check messages — should have the user message + project selection prompt
        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        messages = resp.json()["messages"]
        agent_msgs = [m for m in messages if m["role"] == "agent"]
        assert len(agent_msgs) >= 1
        last_content = agent_msgs[-1]["content"].lower()
        assert "project" in last_content

    def test_workflow_trigger_with_project_dispatches_immediately(self, client: TestClient) -> None:
        """A workflow-triggering message with project_id should dispatch without prompting."""
        client.post("/api/v1/projects", json={"name": "My Project", "project_id": "proj-2"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-2",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        messages = resp.json()["messages"]
        agent_msgs = [m for m in messages if m["role"] == "agent"]
        assert len(agent_msgs) >= 1
        # Should NOT be asking "which project"
        assert "which project" not in agent_msgs[-1]["content"].lower()

    def test_project_selection_by_number(self, client: TestClient) -> None:
        """User can select a project by number after being prompted."""
        client.post("/api/v1/projects", json={"name": "Alpha", "project_id": "proj-a"})
        client.post("/api/v1/projects", json={"name": "Beta", "project_id": "proj-b"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        conv_id = resp.json()["conversation_id"]

        # Reply with project number
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "user1", "message": "1"},
        )
        assert resp.status_code == 201

        # Check that project was set
        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        assert resp.json()["project_id"] is not None

    def test_project_selection_by_name(self, client: TestClient) -> None:
        """User can select a project by name after being prompted."""
        client.post("/api/v1/projects", json={"name": "Alpha", "project_id": "proj-alpha"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        conv_id = resp.json()["conversation_id"]

        # Reply with project name
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "user1", "message": "Alpha"},
        )
        assert resp.status_code == 201

        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        assert resp.json()["project_id"] == "proj-alpha"

    def test_invalid_project_selection_retries(self, client: TestClient) -> None:
        """Invalid project selection should ask again."""
        client.post("/api/v1/projects", json={"name": "Alpha", "project_id": "proj-x"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        conv_id = resp.json()["conversation_id"]

        # Reply with invalid name
        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "user1", "message": "NonexistentProject"},
        )
        assert resp.status_code == 201

        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        messages = resp.json()["messages"]
        agent_msgs = [m for m in messages if m["role"] == "agent"]
        assert "didn't recognise" in agent_msgs[-1]["content"].lower()

    def test_no_projects_shows_helpful_message(self, client: TestClient) -> None:
        """If no projects exist, show a helpful message."""
        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        conv_id = resp.json()["conversation_id"]

        resp = client.get(f"/api/v1/chat/conversations/{conv_id}")
        messages = resp.json()["messages"]
        agent_msgs = [m for m in messages if m["role"] == "agent"]
        last_content = agent_msgs[-1]["content"].lower()
        assert "no project" in last_content or "create a project" in last_content


class TestConversationWorkflowStatus:
    """After dispatching a workflow, conversation should store tracking IDs."""

    def test_dispatch_stores_work_item_and_run_ids(self, client: TestClient) -> None:
        """work_item_id and run_id should be set on conversation after dispatch."""
        client.post("/api/v1/projects", json={"name": "StatusProj", "project_id": "proj-st"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-st",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        # Query the status endpoint
        resp = client.get(f"/api/v1/chat/conversations/{conv_id}/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status["project_id"] == "proj-st"
        assert status["work_item_id"] is not None
        assert status["run_id"] is not None

    def test_status_endpoint_404_for_missing_conversation(self, client: TestClient) -> None:
        resp = client.get("/api/v1/chat/conversations/nonexistent/status")
        assert resp.status_code == 404


class TestPipelineAndTriggerCreation:
    """Dispatching a workflow should create PipelineRun and Trigger records."""

    def test_dispatch_creates_pipeline_run(self, client: TestClient) -> None:
        """A dispatched workflow should create a PipelineRun in the pipeline store."""
        client.post("/api/v1/projects", json={"name": "PipeProj", "project_id": "proj-pipe"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-pipe",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201

        # Check that a pipeline run was created for this project
        resp = client.get("/api/v1/pipelines", params={"project_id": "proj-pipe"})
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) >= 1
        run = runs[0]
        assert run["project_id"] == "proj-pipe"
        assert run["status"] == "running"
        assert run["trigger_type"].startswith("chat:")
        assert run["workflow_definition_id"] == "feature_to_pr"
        # Should have stages
        assert len(run["stages"]) > 0

    def test_dispatch_creates_trigger(self, client: TestClient) -> None:
        """A dispatched workflow should create a Trigger record."""
        client.post("/api/v1/projects", json={"name": "TrigProj", "project_id": "proj-trig"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-trig",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201

        # Check that a trigger was created for this project
        resp = client.get("/api/v1/triggers", params={"project_id": "proj-trig"})
        assert resp.status_code == 200
        triggers = resp.json()
        assert len(triggers) >= 1
        trigger = triggers[0]
        assert trigger["project_id"] == "proj-trig"
        assert trigger["trigger_type"] == "chat"
        assert trigger["name"].startswith("chat:")

    def test_dispatch_links_trigger_to_pipeline(self, client: TestClient) -> None:
        """The PipelineRun should reference the Trigger's ID."""
        client.post("/api/v1/projects", json={"name": "LinkProj", "project_id": "proj-link"})

        client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-link",
                "message": "implement a new login page with OAuth support please",
            },
        )

        runs = client.get(
            "/api/v1/pipelines",
            params={"project_id": "proj-link"},
        ).json()
        triggers = client.get(
            "/api/v1/triggers",
            params={"project_id": "proj-link"},
        ).json()

        assert len(runs) >= 1
        assert len(triggers) >= 1
        assert runs[0]["trigger_id"] == triggers[0]["trigger_id"]


class TestAuditEntryEmission:
    """Dispatching a workflow should emit audit entries."""

    def test_workflow_dispatch_creates_audit_entry(self, client: TestClient) -> None:
        """A dispatched workflow should record a workflow_started audit entry."""
        client.post("/api/v1/projects", json={"name": "AuditProj", "project_id": "proj-aud"})

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "project_id": "proj-aud",
                "message": "implement a new login page with OAuth support please",
            },
        )
        assert resp.status_code == 201

        resp = client.get("/api/v1/audit", params={"resource_type": "work_item"})
        assert resp.status_code == 200
        entries = resp.json()["items"]
        started = [e for e in entries if e["action"] == "workflow_started"]
        assert len(started) >= 1
        assert started[0]["actor_type"] == "system"
        assert started[0]["details"]["workflow_type"] == "feature_to_pr"

    def test_project_selection_creates_audit_entry(self, client: TestClient) -> None:
        """Selecting a project after being prompted should record an audit entry."""
        client.post(
            "/api/v1/projects",
            json={"name": "SelProj", "project_id": "proj-sel"},
        )

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user1",
                "message": "implement a new login page with OAuth support please",
            },
        )
        conv_id = resp.json()["conversation_id"]

        # Select project by number
        client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "user1", "message": "1"},
        )

        resp = client.get(
            "/api/v1/audit",
            params={"resource_type": "conversation"},
        )
        assert resp.status_code == 200
        entries = resp.json()["items"]
        selected = [e for e in entries if e["action"] == "project_selected"]
        assert len(selected) >= 1
        assert selected[0]["actor_id"] == "user1"
        assert selected[0]["resource_id"] == conv_id
        assert selected[0]["details"]["project_id"] == "proj-sel"
