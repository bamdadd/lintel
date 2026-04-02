"""Tests for SpecWorkshop (REQ-F022)."""

from __future__ import annotations

import pytest

from lintel.domain.specs import SpecStatus, SpecWorkshop


class TestSpecWorkshop:
    """SpecWorkshop unit tests."""

    def test_create_spec(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("My Spec", "alice")
        assert spec.title == "My Spec"
        assert spec.created_by == "alice"
        assert spec.status == SpecStatus.DRAFT
        assert spec.sections == ()
        assert spec.version == 1

    def test_add_section(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        updated = ws.add_section(spec.spec_id, "Intro", "Hello", "bob")
        assert len(updated.sections) == 1
        assert updated.sections[0].title == "Intro"
        assert updated.sections[0].content == "Hello"
        assert updated.sections[0].author == "bob"

    def test_update_section(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        spec = ws.add_section(spec.spec_id, "Intro", "v1", "bob")
        section_id = spec.sections[0].section_id
        updated = ws.update_section(spec.spec_id, section_id, "v2")
        assert updated.sections[0].content == "v2"
        assert updated.sections[0].version == 2

    def test_update_section_not_found(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        with pytest.raises(KeyError, match="not found"):
            ws.update_section(spec.spec_id, "bad-id", "x")

    def test_submit_for_review(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        updated = ws.submit_for_review(spec.spec_id, ("bob", "carol"))
        assert updated.status == SpecStatus.IN_REVIEW
        assert updated.reviewers == ("bob", "carol")

    def test_submit_for_review_wrong_status(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        ws.submit_for_review(spec.spec_id, ("bob",))
        with pytest.raises(ValueError, match="not in draft"):
            ws.submit_for_review(spec.spec_id, ("carol",))

    def test_approve(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        ws.submit_for_review(spec.spec_id, ("bob",))
        approved = ws.approve(spec.spec_id)
        assert approved.status == SpecStatus.APPROVED
        assert approved.version == 2

    def test_approve_wrong_status(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        with pytest.raises(ValueError, match="not in review"):
            ws.approve(spec.spec_id)

    def test_add_and_resolve_comment(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        spec = ws.add_section(spec.spec_id, "Intro", "text", "bob")
        section_id = spec.sections[0].section_id
        comment = ws.add_comment(spec.spec_id, section_id, "carol", "Fix typo")
        assert not comment.resolved
        resolved = ws.resolve_comment(spec.spec_id, comment.comment_id)
        assert resolved.resolved

    def test_resolve_comment_not_found(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        with pytest.raises(KeyError, match="not found"):
            ws.resolve_comment(spec.spec_id, "bad-id")

    def test_get_spec(self) -> None:
        ws = SpecWorkshop()
        spec = ws.create_spec("S", "alice")
        fetched = ws.get_spec(spec.spec_id)
        assert fetched.spec_id == spec.spec_id

    def test_get_spec_not_found(self) -> None:
        ws = SpecWorkshop()
        with pytest.raises(KeyError, match="not found"):
            ws.get_spec("nonexistent")

    def test_list_specs_no_filter(self) -> None:
        ws = SpecWorkshop()
        ws.create_spec("A", "alice")
        ws.create_spec("B", "bob")
        assert len(ws.list_specs()) == 2

    def test_list_specs_with_filter(self) -> None:
        ws = SpecWorkshop()
        s1 = ws.create_spec("A", "alice")
        ws.create_spec("B", "bob")
        ws.submit_for_review(s1.spec_id, ("carol",))
        drafts = ws.list_specs(status_filter=SpecStatus.DRAFT)
        assert len(drafts) == 1
        in_review = ws.list_specs(status_filter=SpecStatus.IN_REVIEW)
        assert len(in_review) == 1
