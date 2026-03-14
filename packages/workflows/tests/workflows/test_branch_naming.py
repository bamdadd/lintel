"""Tests for the branch naming convention helper."""

from __future__ import annotations

from lintel.workflows.nodes._branch_naming import BranchNaming, generate_branch_name


class TestGenerateBranchName:
    def test_feature_branch(self) -> None:
        result = generate_branch_name("abc12345def", work_type="feature", description="add login")
        assert result == "lintel/feat/abc12345-add-login"

    def test_bug_branch(self) -> None:
        result = generate_branch_name("bug99999xx", work_type="bug", description="fix crash")
        assert result == "lintel/fix/bug99999-fix-crash"

    def test_refactor_branch(self) -> None:
        result = generate_branch_name("ref00001", work_type="refactor", description="clean up")
        assert result == "lintel/refactor/ref00001-clean-up"

    def test_unknown_type_defaults_to_task(self) -> None:
        result = generate_branch_name("id123456", work_type="chore", description="bump deps")
        assert result == "lintel/task/id123456-bump-deps"

    def test_empty_description(self) -> None:
        result = generate_branch_name("abcdef12", work_type="feature")
        assert result == "lintel/feat/abcdef12"

    def test_truncation_of_long_description(self) -> None:
        long_desc = "this is a very long description that exceeds forty characters limit"
        result = generate_branch_name("id123456", work_type="feature", description=long_desc)
        # slug part should be at most 40 chars
        slug = result.split("/", 2)[2].split("-", 1)[1]  # after <id>-
        assert len(slug) <= 40

    def test_special_characters_in_description(self) -> None:
        result = generate_branch_name(
            "id123456",
            work_type="feature",
            description="fix: crash @login (v2)!",
        )
        assert result == "lintel/feat/id123456-fix-crash-login-v2"

    def test_id_truncated_to_8_chars(self) -> None:
        result = generate_branch_name("abcdef1234567890", work_type="feature")
        assert result == "lintel/feat/abcdef12"

    def test_feat_shorthand_preserved(self) -> None:
        """If work_type is already 'feat', it stays 'feat'."""
        result = generate_branch_name("id000000", work_type="feat")
        assert result == "lintel/feat/id000000"

    def test_trailing_hyphens_stripped(self) -> None:
        result = generate_branch_name(
            "id123456",
            work_type="feature",
            description="hello---",
        )
        assert result == "lintel/feat/id123456-hello"


class TestBranchNaming:
    """Tests for the BranchNaming class interface."""

    def test_generate_classmethod_matches_wrapper(self) -> None:
        result = BranchNaming.generate("abc12345def", work_type="feature", description="add login")
        assert result == "lintel/feat/abc12345-add-login"

    def test_type_map_is_class_constant(self) -> None:
        assert BranchNaming._TYPE_MAP["feature"] == "feat"
        assert BranchNaming._TYPE_MAP["bug"] == "fix"
        assert BranchNaming._TYPE_MAP["refactor"] == "refactor"

    def test_generate_no_description(self) -> None:
        result = BranchNaming.generate("abcdef12", work_type="feature")
        assert result == "lintel/feat/abcdef12"

    def test_generate_unknown_type(self) -> None:
        result = BranchNaming.generate("id123456", work_type="chore", description="bump")
        assert result == "lintel/task/id123456-bump"
