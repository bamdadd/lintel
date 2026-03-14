"""Tests for seed data integrity."""

from __future__ import annotations

from lintel.api.domain.seed import DEFAULT_AGENTS, DEFAULT_SKILLS, DEFAULT_WORKFLOW_DEFINITIONS


class TestDefaultAgents:
    def test_all_agents_have_unique_ids(self) -> None:
        ids = [a.agent_id for a in DEFAULT_AGENTS]
        assert len(ids) == len(set(ids))

    def test_all_agents_have_unique_names(self) -> None:
        names = [a.name for a in DEFAULT_AGENTS]
        assert len(names) == len(set(names))

    def test_all_agents_are_builtin(self) -> None:
        for agent in DEFAULT_AGENTS:
            assert agent.is_builtin is True

    def test_all_agents_have_system_prompt(self) -> None:
        for agent in DEFAULT_AGENTS:
            assert len(agent.system_prompt) > 0

    def test_all_agents_have_tags(self) -> None:
        for agent in DEFAULT_AGENTS:
            assert len(agent.tags) > 0

    def test_agent_count(self) -> None:
        assert len(DEFAULT_AGENTS) >= 10


class TestDefaultSkills:
    def test_all_skills_have_unique_ids(self) -> None:
        ids = [s.skill_id for s in DEFAULT_SKILLS]
        assert len(ids) == len(set(ids))

    def test_all_skills_have_unique_names(self) -> None:
        names = [s.name for s in DEFAULT_SKILLS]
        assert len(names) == len(set(names))

    def test_all_skills_are_builtin(self) -> None:
        for skill in DEFAULT_SKILLS:
            assert skill.is_builtin is True

    def test_all_skills_have_allowed_roles(self) -> None:
        for skill in DEFAULT_SKILLS:
            assert len(skill.allowed_agent_roles) > 0

    def test_skill_count(self) -> None:
        assert len(DEFAULT_SKILLS) >= 15


class TestDefaultWorkflowDefinitions:
    def test_all_definitions_have_unique_ids(self) -> None:
        ids = [d.definition_id for d in DEFAULT_WORKFLOW_DEFINITIONS]
        assert len(ids) == len(set(ids))

    def test_all_definitions_are_templates(self) -> None:
        for defn in DEFAULT_WORKFLOW_DEFINITIONS:
            assert defn.is_template is True

    def test_all_definitions_are_builtin(self) -> None:
        for defn in DEFAULT_WORKFLOW_DEFINITIONS:
            assert defn.is_builtin is True

    def test_all_definitions_have_entry_point(self) -> None:
        for defn in DEFAULT_WORKFLOW_DEFINITIONS:
            assert len(defn.entry_point) > 0

    def test_entry_point_is_in_graph_nodes(self) -> None:
        for defn in DEFAULT_WORKFLOW_DEFINITIONS:
            assert defn.entry_point in defn.graph_nodes, (
                f"{defn.definition_id}: entry_point '{defn.entry_point}' not in graph_nodes"
            )

    def test_edge_nodes_exist_in_graph(self) -> None:
        for defn in DEFAULT_WORKFLOW_DEFINITIONS:
            for src, dst in defn.graph_edges:
                assert src in defn.graph_nodes, (
                    f"{defn.definition_id}: edge source '{src}' not in graph_nodes"
                )
                assert dst in defn.graph_nodes, (
                    f"{defn.definition_id}: edge dest '{dst}' not in graph_nodes"
                )

    def test_definition_count(self) -> None:
        assert len(DEFAULT_WORKFLOW_DEFINITIONS) >= 8

    def test_known_definitions_exist(self) -> None:
        ids = {d.definition_id for d in DEFAULT_WORKFLOW_DEFINITIONS}
        expected = {"feature_to_pr", "bug_fix", "code_review", "refactor", "security_audit"}
        assert expected.issubset(ids)
