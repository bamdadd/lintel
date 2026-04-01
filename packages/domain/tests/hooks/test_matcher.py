"""Unit tests for hook event pattern matcher."""

from __future__ import annotations

from lintel.domain.hooks.matcher import find_matching_hooks, match
from lintel.domain.types import HookType, Trigger, TriggerType


class TestMatch:
    """Tests for match() function."""

    def test_exact_match(self) -> None:
        assert match("pipeline.build.completed", "pipeline.build.completed") is True

    def test_exact_no_match(self) -> None:
        assert match("pipeline.build.completed", "pipeline.test.completed") is False

    def test_single_wildcard(self) -> None:
        assert match("pipeline.*.completed", "pipeline.build.completed") is True

    def test_single_wildcard_no_match(self) -> None:
        assert match("pipeline.*.completed", "pipeline.build.failed") is False

    def test_star_matches_all(self) -> None:
        assert match("*", "anything.here") is True

    def test_empty_pattern_matches_all(self) -> None:
        assert match("", "anything") is True

    def test_prefix_wildcard(self) -> None:
        assert match("Pipeline*", "PipelineRunCompleted") is True

    def test_suffix_wildcard(self) -> None:
        assert match("*.completed", "pipeline.build.completed") is True

    def test_question_mark_wildcard(self) -> None:
        assert match("pipeline.?.completed", "pipeline.X.completed") is True

    def test_question_mark_no_match(self) -> None:
        assert match("pipeline.?.completed", "pipeline.build.completed") is False

    def test_bracket_pattern(self) -> None:
        assert match("pipeline.[bt]est.completed", "pipeline.test.completed") is True

    def test_case_sensitive(self) -> None:
        assert match("Pipeline*", "pipelineRunCompleted") is False

    def test_multi_segment_glob(self) -> None:
        assert match("*.*.completed", "pipeline.build.completed") is True

    def test_no_match_different_structure(self) -> None:
        assert match("a.b.c", "x.y.z") is False


def _make_hook_trigger(
    trigger_id: str = "t1",
    hook_type: HookType = HookType.POST,
    event_pattern: str = "pipeline.*.completed",
    enabled: bool = True,
) -> Trigger:
    return Trigger(
        trigger_id=trigger_id,
        project_id="proj-1",
        trigger_type=TriggerType.WEBHOOK,
        name="Test Hook",
        hook_type=hook_type,
        event_pattern=event_pattern,
        enabled=enabled,
    )


class TestFindMatchingHooks:
    """Tests for find_matching_hooks() function."""

    def test_matching_hook_returned(self) -> None:
        hooks = [_make_hook_trigger()]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 1
        assert result[0].trigger_id == "t1"

    def test_non_matching_hook_excluded(self) -> None:
        hooks = [_make_hook_trigger(event_pattern="deploy.*")]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 0

    def test_disabled_hook_excluded(self) -> None:
        hooks = [_make_hook_trigger(enabled=False)]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 0

    def test_hook_without_hook_type_excluded(self) -> None:
        trigger = Trigger(
            trigger_id="t1",
            project_id="proj-1",
            trigger_type=TriggerType.WEBHOOK,
            name="Regular Trigger",
        )
        result = find_matching_hooks("pipeline.build.completed", [trigger])
        assert len(result) == 0

    def test_hook_without_event_pattern_excluded(self) -> None:
        trigger = Trigger(
            trigger_id="t1",
            project_id="proj-1",
            trigger_type=TriggerType.WEBHOOK,
            name="No Pattern",
            hook_type=HookType.POST,
        )
        result = find_matching_hooks("pipeline.build.completed", [trigger])
        assert len(result) == 0

    def test_empty_hooks_list(self) -> None:
        result = find_matching_hooks("pipeline.build.completed", [])
        assert len(result) == 0

    def test_multiple_matching_hooks(self) -> None:
        hooks = [
            _make_hook_trigger(trigger_id="t1", event_pattern="pipeline.*.*"),
            _make_hook_trigger(trigger_id="t2", event_pattern="*.build.*"),
        ]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 2

    def test_mixed_matching_and_non_matching(self) -> None:
        hooks = [
            _make_hook_trigger(trigger_id="t1", event_pattern="pipeline.*.*"),
            _make_hook_trigger(trigger_id="t2", event_pattern="deploy.*"),
        ]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 1
        assert result[0].trigger_id == "t1"

    def test_pre_and_post_hooks_both_returned(self) -> None:
        hooks = [
            _make_hook_trigger(trigger_id="t1", hook_type=HookType.PRE),
            _make_hook_trigger(trigger_id="t2", hook_type=HookType.POST),
        ]
        result = find_matching_hooks("pipeline.build.completed", hooks)
        assert len(result) == 2
