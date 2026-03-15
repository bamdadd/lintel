"""Tests for command schemas."""

from __future__ import annotations

import dataclasses
from uuid import UUID

import pytest

from lintel.agents.commands import ScheduleAgentStep, ScheduleSandboxJob
from lintel.agents.types import AgentRole
from lintel.contracts.types import ThreadRef
from lintel.pii.commands import RevealPII
from lintel.slack.commands import GrantApproval, ProcessIncomingMessage, RejectApproval
from lintel.workflows.commands import StartWorkflow

REF = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")


class TestCommandsFrozen:
    def test_all_commands_frozen(self) -> None:
        commands = [
            ProcessIncomingMessage(
                thread_ref=REF,
                raw_text="hi",
                sender_id="U1",
                sender_name="Bob",
            ),
            StartWorkflow(thread_ref=REF, workflow_type="feature"),
            ScheduleAgentStep(
                thread_ref=REF,
                agent_role=AgentRole.CODER,
                step_name="implement",
            ),
            ScheduleSandboxJob(
                thread_ref=REF,
                agent_role=AgentRole.CODER,
                repo_url="r",
                base_sha="abc",
            ),
            GrantApproval(
                thread_ref=REF,
                gate_type="spec",
                approver_id="U1",
                approver_name="Bob",
            ),
            RejectApproval(
                thread_ref=REF,
                gate_type="spec",
                rejector_id="U1",
                reason="no",
            ),
            RevealPII(
                thread_ref=REF,
                placeholder="<PII_1>",
                requester_id="U1",
                reason="debug",
            ),
        ]
        for cmd in commands:
            assert dataclasses.is_dataclass(cmd)
            with pytest.raises(dataclasses.FrozenInstanceError):
                cmd.thread_ref = REF  # type: ignore[misc]


class TestCommandDefaults:
    def test_process_incoming_message_has_idempotency_key(self) -> None:
        cmd = ProcessIncomingMessage(
            thread_ref=REF,
            raw_text="hi",
            sender_id="U1",
            sender_name="Bob",
        )
        assert cmd.idempotency_key is not None
        assert len(cmd.idempotency_key) > 0

    def test_process_incoming_message_unique_keys(self) -> None:
        cmd1 = ProcessIncomingMessage(
            thread_ref=REF,
            raw_text="hi",
            sender_id="U1",
            sender_name="Bob",
        )
        cmd2 = ProcessIncomingMessage(
            thread_ref=REF,
            raw_text="hi",
            sender_id="U1",
            sender_name="Bob",
        )
        assert cmd1.idempotency_key != cmd2.idempotency_key

    def test_start_workflow_has_correlation_id(self) -> None:
        cmd = StartWorkflow(thread_ref=REF, workflow_type="feature")
        assert isinstance(cmd.correlation_id, UUID)

    def test_schedule_sandbox_job_defaults(self) -> None:
        cmd = ScheduleSandboxJob(
            thread_ref=REF,
            agent_role=AgentRole.CODER,
            repo_url="r",
            base_sha="abc",
        )
        assert cmd.commands == []
        assert isinstance(cmd.correlation_id, UUID)

    def test_schedule_agent_step_defaults(self) -> None:
        cmd = ScheduleAgentStep(
            thread_ref=REF,
            agent_role=AgentRole.PLANNER,
            step_name="plan",
        )
        assert cmd.context == {}

    def test_grant_approval_defaults(self) -> None:
        cmd = GrantApproval(
            thread_ref=REF,
            gate_type="spec",
            approver_id="U1",
            approver_name="Alice",
        )
        assert isinstance(cmd.correlation_id, UUID)
        assert cmd.gate_type == "spec"
        assert cmd.approver_name == "Alice"

    def test_reject_approval_defaults(self) -> None:
        cmd = RejectApproval(
            thread_ref=REF,
            gate_type="pr",
            rejector_id="U2",
            reason="needs changes",
        )
        assert isinstance(cmd.correlation_id, UUID)
        assert cmd.reason == "needs changes"

    def test_reveal_pii_defaults(self) -> None:
        cmd = RevealPII(
            thread_ref=REF,
            placeholder="<EMAIL_1>",
            requester_id="U3",
            reason="support ticket",
        )
        assert isinstance(cmd.correlation_id, UUID)
        assert cmd.placeholder == "<EMAIL_1>"
        assert cmd.reason == "support ticket"


class TestStartWorkflowContinuation:
    def test_continue_from_run_id_defaults_empty(self) -> None:
        cmd = StartWorkflow(thread_ref=REF, workflow_type="feature_to_pr")
        assert cmd.continue_from_run_id == ""

    def test_continue_from_run_id_set(self) -> None:
        cmd = StartWorkflow(
            thread_ref=REF,
            workflow_type="feature_to_pr",
            continue_from_run_id="prev-run-123",
        )
        assert cmd.continue_from_run_id == "prev-run-123"


class TestCommandUniqueCorrelationIds:
    def test_each_command_gets_unique_correlation_id(self) -> None:
        ids = set()
        for _ in range(10):
            cmd = StartWorkflow(thread_ref=REF, workflow_type="feature")
            ids.add(cmd.correlation_id)
        assert len(ids) == 10
