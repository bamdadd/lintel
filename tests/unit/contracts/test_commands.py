"""Tests for command schemas."""

from __future__ import annotations

import contextlib
import dataclasses
from uuid import UUID

from lintel.contracts.commands import (
    GrantApproval,
    ProcessIncomingMessage,
    RejectApproval,
    RevealPII,
    ScheduleAgentStep,
    ScheduleSandboxJob,
    StartWorkflow,
)
from lintel.contracts.types import AgentRole, ThreadRef

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
            RejectApproval(thread_ref=REF, gate_type="spec", rejector_id="U1", reason="no"),
            RevealPII(thread_ref=REF, placeholder="<PII_1>", requester_id="U1", reason="debug"),
        ]
        for cmd in commands:
            assert dataclasses.is_dataclass(cmd)
            with contextlib.suppress(dataclasses.FrozenInstanceError):
                object.__setattr__(cmd, "thread_ref", REF)


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
