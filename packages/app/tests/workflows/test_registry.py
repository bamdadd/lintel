"""Tests for the workflow graph registry."""

from __future__ import annotations

import pytest
from lintel.workflows.registry import WORKFLOW_BUILDERS, get_workflow_builder


class TestWorkflowRegistry:
    @pytest.mark.parametrize("definition_id", list(WORKFLOW_BUILDERS.keys()))
    def test_all_builders_produce_valid_graphs(self, definition_id: str) -> None:
        builder = get_workflow_builder(definition_id)
        graph = builder()
        assert len(graph.nodes) >= 2
        compiled = graph.compile()
        assert compiled is not None

    def test_unknown_workflow_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown workflow"):
            get_workflow_builder("nonexistent")

    def test_feature_to_pr_has_implement_node(self) -> None:
        builder = get_workflow_builder("feature_to_pr")
        graph = builder()
        assert "implement" in graph.nodes

    def test_bug_fix_has_triage_node(self) -> None:
        builder = get_workflow_builder("bug_fix")
        graph = builder()
        assert "triage" in graph.nodes

    def test_security_audit_has_scan_nodes(self) -> None:
        builder = get_workflow_builder("security_audit")
        graph = builder()
        assert "dependency_scan" in graph.nodes
        assert "code_scan" in graph.nodes
        assert "secret_scan" in graph.nodes
