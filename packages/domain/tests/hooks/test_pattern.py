"""Tests for event pattern matching."""

from __future__ import annotations

from lintel.domain.hooks.pattern import conditions_match, matches_event_pattern, resolve_params


class TestMatchesEventPattern:
    def test_exact_match(self) -> None:
        assert matches_event_pattern("PipelineRunCompleted", "PipelineRunCompleted")

    def test_wildcard_all(self) -> None:
        assert matches_event_pattern("*", "anything")

    def test_empty_matches_all(self) -> None:
        assert matches_event_pattern("", "anything")

    def test_glob_prefix(self) -> None:
        assert matches_event_pattern("Pipeline*", "PipelineRunCompleted")
        assert not matches_event_pattern("Pipeline*", "WorkItemCreated")

    def test_glob_suffix(self) -> None:
        assert matches_event_pattern("*Completed", "PipelineRunCompleted")
        assert not matches_event_pattern("*Completed", "PipelineRunStarted")

    def test_question_mark(self) -> None:
        assert matches_event_pattern("Work?????reated", "WorkItemCreated")
        assert not matches_event_pattern("Work?????reated", "WorkItemUpdated")

    def test_no_match(self) -> None:
        assert not matches_event_pattern("WorkItemCreated", "PipelineRunCompleted")


class TestConditionsMatch:
    def test_empty_conditions(self) -> None:
        assert conditions_match({}, {"any": "thing"})

    def test_matching(self) -> None:
        assert conditions_match({"stage": "review"}, {"stage": "review", "x": 1})

    def test_not_matching(self) -> None:
        assert not conditions_match({"stage": "review"}, {"stage": "deploy"})

    def test_missing_key(self) -> None:
        assert not conditions_match({"stage": "review"}, {})


class TestResolveParams:
    def test_none_template(self) -> None:
        assert resolve_params(None, {"x": 1}) == {}

    def test_literal_values(self) -> None:
        assert resolve_params({"key": "literal"}, {}) == {"key": "literal"}

    def test_template_substitution(self) -> None:
        result = resolve_params(
            {"commit": "{{ event.sha }}", "branch": "{{ event.ref }}"},
            {"sha": "abc123", "ref": "main"},
        )
        assert result == {"commit": "abc123", "branch": "main"}

    def test_missing_field_returns_empty(self) -> None:
        assert resolve_params({"x": "{{ event.missing }}"}, {}) == {"x": ""}
