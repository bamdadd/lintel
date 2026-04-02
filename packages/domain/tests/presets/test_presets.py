"""Tests for workflow presets domain model."""

from __future__ import annotations

from lintel.domain.presets import (
    PresetCategory,
    PresetManager,
    PresetOverride,
    WorkflowPreset,
)


def _make_preset(
    preset_id: str = "p1",
    name: str = "Fast",
    category: PresetCategory = PresetCategory.SPEED,
    overrides: tuple[PresetOverride, ...] = (),
    compatible_workflows: tuple[str, ...] = (),
    priority: int = 0,
) -> WorkflowPreset:
    return WorkflowPreset(
        preset_id=preset_id,
        name=name,
        category=category,
        overrides=overrides,
        compatible_workflows=compatible_workflows,
        priority=priority,
    )


# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------


class TestPresetOverride:
    def test_frozen(self) -> None:
        o = PresetOverride(key="k", value="v", description="d")
        assert o.key == "k"

    def test_default_description(self) -> None:
        o = PresetOverride(key="k", value=1)
        assert o.description == ""


class TestWorkflowPreset:
    def test_as_dict(self) -> None:
        p = _make_preset(
            overrides=(
                PresetOverride(key="a", value=1),
                PresetOverride(key="b", value="x"),
            ),
        )
        assert p.as_dict() == {"a": 1, "b": "x"}

    def test_override_keys(self) -> None:
        p = _make_preset(
            overrides=(
                PresetOverride(key="a", value=1),
                PresetOverride(key="b", value=2),
            ),
        )
        assert p.override_keys == frozenset({"a", "b"})

    def test_ordering(self) -> None:
        low = _make_preset(priority=1)
        high = _make_preset(priority=10)
        assert low < high
        assert high > low
        assert low <= high
        assert high >= low


# ------------------------------------------------------------------
# Manager
# ------------------------------------------------------------------


class TestPresetManager:
    def test_register_and_get(self) -> None:
        mgr = PresetManager()
        p = _make_preset()
        mgr.register(p)
        assert mgr.get("p1") is p

    def test_get_missing(self) -> None:
        mgr = PresetManager()
        assert mgr.get("nope") is None

    def test_list_all(self) -> None:
        mgr = PresetManager()
        mgr.register(_make_preset(preset_id="a", name="A", category=PresetCategory.SPEED))
        mgr.register(_make_preset(preset_id="b", name="B", category=PresetCategory.QUALITY))
        assert len(mgr.list()) == 2

    def test_list_filtered(self) -> None:
        mgr = PresetManager()
        mgr.register(_make_preset(preset_id="a", category=PresetCategory.SPEED))
        mgr.register(_make_preset(preset_id="b", category=PresetCategory.QUALITY))
        assert len(mgr.list(category_filter=PresetCategory.SPEED)) == 1

    def test_compose_merges_by_priority(self) -> None:
        mgr = PresetManager()
        mgr.register(
            _make_preset(
                preset_id="low",
                priority=1,
                overrides=(
                    PresetOverride(key="timeout", value=30),
                    PresetOverride(key="retries", value=3),
                ),
            )
        )
        mgr.register(
            _make_preset(
                preset_id="high",
                priority=10,
                overrides=(PresetOverride(key="timeout", value=120),),
            )
        )
        result = mgr.compose(["low", "high"])
        # high-priority preset wins for 'timeout'
        assert result["timeout"] == 120
        # low-priority 'retries' survives
        assert result["retries"] == 3

    def test_compose_skips_unknown(self) -> None:
        mgr = PresetManager()
        mgr.register(_make_preset(preset_id="a", overrides=(PresetOverride("k", 1),)))
        result = mgr.compose(["a", "missing"])
        assert result == {"k": 1}

    def test_validate_compatibility_ok(self) -> None:
        mgr = PresetManager()
        mgr.register(_make_preset(preset_id="a", compatible_workflows=("feature_to_pr",)))
        assert mgr.validate_compatibility(["a"], "feature_to_pr") == []

    def test_validate_compatibility_incompatible(self) -> None:
        mgr = PresetManager()
        mgr.register(
            _make_preset(preset_id="a", name="Fast", compatible_workflows=("feature_to_pr",))
        )
        conflicts = mgr.validate_compatibility(["a"], "review")
        assert len(conflicts) == 1
        assert "not compatible" in conflicts[0]

    def test_validate_compatibility_missing_preset(self) -> None:
        mgr = PresetManager()
        conflicts = mgr.validate_compatibility(["nope"], "any")
        assert len(conflicts) == 1
        assert "not found" in conflicts[0]

    def test_validate_compatibility_empty_compatible_workflows(self) -> None:
        mgr = PresetManager()
        mgr.register(_make_preset(preset_id="a", compatible_workflows=()))
        # Empty compatible_workflows means compatible with everything
        assert mgr.validate_compatibility(["a"], "anything") == []
