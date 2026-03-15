"""Tests for core domain types."""

from __future__ import annotations

import dataclasses
from uuid import UUID, uuid4

from lintel.agents.types import AgentRole, SkillExecutionMode
from lintel.contracts.types import (
    ActorType,
    ChatSession,
    CorrelationId,
    Environment,
    EnvironmentType,
    EventId,
    PipelineRun,
    Project,
    ProjectStatus,
    ThreadRef,
    Variable,
    WorkflowDefinitionRecord,
    WorkflowPhase,
    WorkflowStepConfig,
)
from lintel.sandbox.types import SandboxStatus


class TestThreadRef:
    def test_stream_id_format(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert ref.stream_id == "thread:W1:C1:123.456"

    def test_str_returns_stream_id(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert str(ref) == ref.stream_id

    def test_frozen(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert dataclasses.is_dataclass(ref)
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            ref.workspace_id = "W2"  # type: ignore[misc]

    def test_equality(self) -> None:
        ref1 = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        ref2 = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        ref3 = ThreadRef(workspace_id="W2", channel_id="C1", thread_ts="1.0")
        assert ref1 == ref2
        assert ref1 != ref3

    def test_hashable(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        assert hash(ref) == hash(ThreadRef("W1", "C1", "1.0"))
        assert {ref} == {ThreadRef("W1", "C1", "1.0")}

    def test_stream_id_with_special_chars(self) -> None:
        ref = ThreadRef(workspace_id="T01", channel_id="C02ABC", thread_ts="1709.123456")
        assert ref.stream_id == "thread:T01:C02ABC:1709.123456"


class TestEnums:
    def test_actor_type_values(self) -> None:
        assert ActorType.HUMAN == "human"
        assert ActorType.AGENT == "agent"
        assert ActorType.SYSTEM == "system"
        assert len(ActorType) == 3

    def test_agent_role_values(self) -> None:
        expected = {
            "planner",
            "coder",
            "reviewer",
            "pm",
            "designer",
            "summarizer",
            "architect",
            "qa_engineer",
            "devops",
            "security",
            "researcher",
            "tech_lead",
            "documentation",
            "triage",
        }
        assert {r.value for r in AgentRole} == expected
        assert len(AgentRole) == 14

    def test_workflow_phase_values(self) -> None:
        assert WorkflowPhase.INGESTING == "ingesting"
        assert WorkflowPhase.CLOSED == "closed"
        assert len(WorkflowPhase) == 8

    def test_workflow_phase_ordering(self) -> None:
        phases = list(WorkflowPhase)
        assert phases[0] == WorkflowPhase.INGESTING
        assert phases[-1] == WorkflowPhase.CLOSED

    def test_sandbox_status_values(self) -> None:
        expected = {
            "pending",
            "creating",
            "running",
            "collecting",
            "completed",
            "failed",
            "destroyed",
        }
        assert {s.value for s in SandboxStatus} == expected
        assert len(SandboxStatus) == 7

    def test_skill_execution_mode_values(self) -> None:
        assert SkillExecutionMode.INLINE == "inline"
        assert SkillExecutionMode.ASYNC_JOB == "async_job"
        assert SkillExecutionMode.SANDBOX == "sandbox"
        assert len(SkillExecutionMode) == 3

    def test_enums_are_str_enums(self) -> None:
        assert isinstance(ActorType.HUMAN, str)
        assert isinstance(AgentRole.CODER, str)
        assert isinstance(WorkflowPhase.PLANNING, str)
        assert isinstance(SandboxStatus.RUNNING, str)
        assert isinstance(SkillExecutionMode.INLINE, str)


class TestNewTypes:
    def test_correlation_id_wraps_uuid(self) -> None:
        raw = uuid4()
        cid = CorrelationId(raw)
        assert cid == raw
        assert isinstance(cid, UUID)

    def test_event_id_wraps_uuid(self) -> None:
        raw = uuid4()
        eid = EventId(raw)
        assert eid == raw
        assert isinstance(eid, UUID)

    def test_newtypes_are_distinct_conceptually(self) -> None:
        raw = uuid4()
        cid = CorrelationId(raw)
        eid = EventId(raw)
        # NewType is erased at runtime, so they are equal
        # but the type checker treats them as distinct
        assert cid == eid


class TestProject:
    def test_project_has_many_repos(self) -> None:
        p = Project(
            project_id="p1",
            name="My Project",
            repo_ids=("repo-1", "repo-2", "repo-3"),
        )
        assert len(p.repo_ids) == 3
        assert "repo-2" in p.repo_ids

    def test_project_defaults(self) -> None:
        p = Project(project_id="p1", name="Minimal")
        assert p.repo_ids == ()
        assert p.credential_ids == ()
        assert p.default_branch == "main"
        assert p.status == ProjectStatus.ACTIVE

    def test_project_no_channel_or_provider_fields(self) -> None:
        p = Project(project_id="p1", name="Test")
        assert not hasattr(p, "channel_id")
        assert not hasattr(p, "workspace_id")
        assert not hasattr(p, "ai_provider_id")
        assert not hasattr(p, "workflow_definition_id")

    def test_project_frozen(self) -> None:
        p = Project(project_id="p1", name="Test")
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            p.name = "Changed"  # type: ignore[misc]


class TestWorkflowStepConfig:
    def test_step_config_defaults(self) -> None:
        sc = WorkflowStepConfig(node_name="plan")
        assert sc.agent_id == ""
        assert sc.model_id == ""
        assert sc.provider_id == ""
        assert sc.requires_approval is False

    def test_step_config_with_all_fields(self) -> None:
        sc = WorkflowStepConfig(
            node_name="implement",
            agent_id="agent_coder",
            model_id="model-claude",
            provider_id="prov-anthropic",
            requires_approval=False,
            label="Implement",
            description="Writes code",
        )
        assert sc.node_name == "implement"
        assert sc.agent_id == "agent_coder"
        assert sc.model_id == "model-claude"
        assert sc.provider_id == "prov-anthropic"

    def test_step_config_approval_gate(self) -> None:
        sc = WorkflowStepConfig(
            node_name="approval_gate_pr",
            requires_approval=True,
            label="Approved for PR",
        )
        assert sc.requires_approval is True

    def test_step_config_frozen(self) -> None:
        sc = WorkflowStepConfig(node_name="plan")
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            sc.node_name = "other"  # type: ignore[misc]


class TestWorkflowDefinitionWithStepConfigs:
    def test_definition_has_step_configs(self) -> None:
        steps = (
            WorkflowStepConfig(node_name="plan", agent_id="agent_planner"),
            WorkflowStepConfig(
                node_name="implement",
                agent_id="agent_coder",
                model_id="m1",
                provider_id="p1",
            ),
            WorkflowStepConfig(
                node_name="approval_gate",
                requires_approval=True,
            ),
        )
        wf = WorkflowDefinitionRecord(
            definition_id="wf1",
            name="Test Workflow",
            step_configs=steps,
        )
        assert len(wf.step_configs) == 3
        assert wf.step_configs[0].agent_id == "agent_planner"
        assert wf.step_configs[1].model_id == "m1"
        assert wf.step_configs[2].requires_approval is True

    def test_definition_preserves_node_metadata(self) -> None:
        wf = WorkflowDefinitionRecord(
            definition_id="wf1",
            name="Test",
            node_metadata=({"node": "plan", "label": "Plan"},),
            step_configs=(WorkflowStepConfig(node_name="plan"),),
        )
        assert len(wf.node_metadata) == 1
        assert len(wf.step_configs) == 1


class TestPipelineRunEnvironment:
    def test_pipeline_run_has_environment_id(self) -> None:
        run = PipelineRun(
            run_id="run-1",
            project_id="p1",
            work_item_id="wi-1",
            workflow_definition_id="wf1",
            environment_id="env-prod",
        )
        assert run.environment_id == "env-prod"

    def test_pipeline_run_environment_defaults_empty(self) -> None:
        run = PipelineRun(
            run_id="run-1",
            project_id="p1",
            work_item_id="wi-1",
            workflow_definition_id="wf1",
        )
        assert run.environment_id == ""


class TestEnvironment:
    def test_environment_no_project_id(self) -> None:
        env = Environment(environment_id="e1", name="Dev")
        assert not hasattr(env, "project_id")

    def test_environment_defaults(self) -> None:
        env = Environment(environment_id="e1", name="Dev")
        assert env.env_type == EnvironmentType.DEVELOPMENT
        assert env.config is None


class TestVariable:
    def test_variable_scoped_to_environment(self) -> None:
        v = Variable(
            variable_id="v1",
            key="DB_HOST",
            value="localhost",
            environment_id="env-dev",
        )
        assert v.environment_id == "env-dev"

    def test_variable_no_project_id(self) -> None:
        v = Variable(variable_id="v1", key="K", value="V")
        assert not hasattr(v, "project_id")


class TestChatSession:
    def test_chat_session_fields(self) -> None:
        cs = ChatSession(
            session_id="cs-1",
            project_id="p1",
            thread_ref_str="thread:W1:C1:1.0",
            mcp_server_ids=("mcp-1", "mcp-2"),
        )
        assert cs.session_id == "cs-1"
        assert cs.project_id == "p1"
        assert len(cs.mcp_server_ids) == 2

    def test_chat_session_defaults(self) -> None:
        cs = ChatSession(session_id="cs-1", project_id="p1")
        assert cs.thread_ref_str == ""
        assert cs.mcp_server_ids == ()

    def test_chat_session_frozen(self) -> None:
        cs = ChatSession(session_id="cs-1", project_id="p1")
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            cs.project_id = "p2"  # type: ignore[misc]
