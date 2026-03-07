"""Tests for workflow nodes: ingest, route, plan, review, analyse, triage, test_code, generic."""

from __future__ import annotations

from typing import Any

import pytest

from lintel.workflows.nodes.analyse import analyse_code
from lintel.workflows.nodes.generic import (
    _stub,
    build_release,
    code_scan,
    codebase_tour,
    complete_onboarding,
    define_scope,
    dependency_scan,
    deploy,
    draft_docs,
    first_task,
    fix_bug,
    generate_report,
    hotfix,
    investigate,
    lint_code,
    notify_release,
    post_mortem,
    prototype,
    publish_docs,
    refactor_code,
    remediate,
    reproduce_bug,
    research,
    secret_scan,
    security_scan,
    send_feedback,
    setup_env,
    version_bump,
    write_changelog,
)
from lintel.workflows.nodes.ingest import ingest_message
from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.route import route_intent
from lintel.workflows.nodes.test_code import run_tests
from lintel.workflows.nodes.triage import triage_issue


class TestIngestNode:
    async def test_returns_current_phase(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["hello"]}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "ingesting"

    async def test_passes_through_sanitized_messages(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["msg1", "msg2"]}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["sanitized_messages"] == ["msg1", "msg2"]

    async def test_empty_messages(self) -> None:
        state: dict[str, Any] = {}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["sanitized_messages"] == []


class TestRouteNode:
    async def test_detects_bug_intent(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["there is a bug in login"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "bug"

    async def test_detects_refactor_intent(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["refactor the database module"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "refactor"

    async def test_defaults_to_feature(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["add a new dashboard page"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "feature"

    async def test_sets_phase_to_planning(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["anything"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "planning"

    async def test_error_keyword_detected(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["error in production"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "bug"

    async def test_clean_keyword_triggers_refactor(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["clean up this module"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "refactor"

    async def test_empty_messages(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": []}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "feature"


class TestPlanNode:
    async def test_produces_plan_with_tasks(self) -> None:
        state: dict[str, Any] = {"intent": "feature"}
        result = await plan_work(state, {"configurable": {}})  # type: ignore[arg-type]
        assert "tasks" in result["plan"]
        assert len(result["plan"]["tasks"]) > 0

    async def test_includes_intent_in_plan(self) -> None:
        state: dict[str, Any] = {"intent": "bug"}
        result = await plan_work(state, {"configurable": {}})  # type: ignore[arg-type]
        assert result["plan"]["intent"] == "bug"

    async def test_sets_approval_phase(self) -> None:
        state: dict[str, Any] = {"intent": "feature"}
        result = await plan_work(state, {"configurable": {}})  # type: ignore[arg-type]
        assert result["current_phase"] == "awaiting_spec_approval"
        assert "spec_approval" in result["pending_approvals"]


class TestReviewNode:
    async def test_sets_merge_approval_phase(self) -> None:
        state: dict[str, Any] = {}
        result = await review_output(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "awaiting_merge_approval"

    async def test_produces_agent_output(self) -> None:
        state: dict[str, Any] = {}
        result = await review_output(state)  # type: ignore[arg-type]
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["role"] == "reviewer"


class TestAnalyseNode:
    async def test_returns_analysis(self) -> None:
        result = await analyse_code({})
        assert result["current_phase"] == "analysing"
        assert result["agent_outputs"][0]["node"] == "analyse"


class TestTriageNode:
    async def test_returns_classification(self) -> None:
        result = await triage_issue({})
        assert result["current_phase"] == "triaging"
        assert result["agent_outputs"][0]["classification"] == "bug"
        assert result["agent_outputs"][0]["priority"] == "P2"


class TestRunTestsNode:
    async def test_returns_passed(self) -> None:
        result = await run_tests({})
        assert result["current_phase"] == "testing"
        assert result["agent_outputs"][0]["verdict"] == "passed"


class TestStubFactory:
    def test_stub_creates_named_function(self) -> None:
        node = _stub("my_node", "my_phase", "my summary")
        assert node.__name__ == "my_node"

    async def test_stub_returns_correct_state(self) -> None:
        node = _stub("test_node", "testing_phase", "test summary")
        result = await node({})
        assert result["current_phase"] == "testing_phase"
        assert result["agent_outputs"][0]["node"] == "test_node"
        assert result["agent_outputs"][0]["summary"] == "test summary"


class TestAllStubNodes:
    """Ensure every stub node runs and returns the expected structure."""

    @pytest.mark.parametrize(
        "node_fn,expected_phase",
        [
            (reproduce_bug, "reproducing"),
            (fix_bug, "fixing"),
            (lint_code, "linting"),
            (security_scan, "scanning"),
            (send_feedback, "feedback"),
            (refactor_code, "refactoring"),
            (dependency_scan, "scanning"),
            (code_scan, "scanning"),
            (secret_scan, "scanning"),
            (generate_report, "reporting"),
            (remediate, "remediating"),
            (investigate, "investigating"),
            (hotfix, "hotfixing"),
            (deploy, "deploying"),
            (post_mortem, "post_mortem"),
            (draft_docs, "drafting"),
            (publish_docs, "publishing"),
            (write_changelog, "changelog"),
            (version_bump, "versioning"),
            (build_release, "building"),
            (notify_release, "notifying"),
            (setup_env, "setup"),
            (codebase_tour, "touring"),
            (first_task, "first_task"),
            (complete_onboarding, "complete"),
            (define_scope, "scoping"),
            (research, "researching"),
            (prototype, "prototyping"),
        ],
    )
    async def test_stub_node(self, node_fn: Any, expected_phase: str) -> None:  # noqa: ANN401
        result = await node_fn({})
        assert result["current_phase"] == expected_phase
        assert len(result["agent_outputs"]) == 1
        assert "node" in result["agent_outputs"][0]
        assert "summary" in result["agent_outputs"][0]
