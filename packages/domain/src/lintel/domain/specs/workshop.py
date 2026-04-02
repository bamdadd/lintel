"""Spec workshop for collaborative spec editing (REQ-F022)."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from lintel.domain.specs.types import Spec, SpecComment, SpecSection, SpecStatus


class SpecWorkshop:
    """Manages collaborative specification editing.

    Holds an in-memory collection of specs and comments, providing
    create / update / review / approve lifecycle operations.
    """

    def __init__(self) -> None:
        self._specs: dict[str, Spec] = {}
        self._comments: dict[str, list[SpecComment]] = {}

    def create_spec(self, title: str, created_by: str) -> Spec:
        """Create a new draft specification."""
        spec = Spec(
            spec_id=uuid.uuid4().hex,
            title=title,
            created_by=created_by,
        )
        self._specs[spec.spec_id] = spec
        self._comments[spec.spec_id] = []
        return spec

    def add_section(
        self,
        spec_id: str,
        title: str,
        content: str,
        author: str,
    ) -> Spec:
        """Add a section to a spec. Raises KeyError if spec not found."""
        spec = self._get_spec(spec_id)
        section = SpecSection(
            section_id=uuid.uuid4().hex,
            title=title,
            content=content,
            author=author,
        )
        updated = _replace_spec(
            spec,
            sections=(*spec.sections, section),
        )
        self._specs[spec_id] = updated
        return updated

    def update_section(
        self,
        spec_id: str,
        section_id: str,
        content: str,
    ) -> Spec:
        """Update section content, bumping section version."""
        spec = self._get_spec(spec_id)
        new_sections: list[SpecSection] = []
        found = False
        for s in spec.sections:
            if s.section_id == section_id:
                found = True
                new_sections.append(
                    SpecSection(
                        section_id=s.section_id,
                        title=s.title,
                        content=content,
                        author=s.author,
                        version=s.version + 1,
                    )
                )
            else:
                new_sections.append(s)
        if not found:
            msg = f"Section {section_id} not found in spec {spec_id}"
            raise KeyError(msg)
        updated = _replace_spec(spec, sections=tuple(new_sections))
        self._specs[spec_id] = updated
        return updated

    def submit_for_review(self, spec_id: str, reviewers: tuple[str, ...]) -> Spec:
        """Move spec from draft to in_review."""
        spec = self._get_spec(spec_id)
        if spec.status != SpecStatus.DRAFT:
            msg = f"Spec {spec_id} is not in draft status"
            raise ValueError(msg)
        updated = _replace_spec(
            spec,
            status=SpecStatus.IN_REVIEW,
            reviewers=reviewers,
        )
        self._specs[spec_id] = updated
        return updated

    def approve(self, spec_id: str) -> Spec:
        """Approve a spec that is in review."""
        spec = self._get_spec(spec_id)
        if spec.status != SpecStatus.IN_REVIEW:
            msg = f"Spec {spec_id} is not in review"
            raise ValueError(msg)
        updated = _replace_spec(
            spec,
            status=SpecStatus.APPROVED,
            version=spec.version + 1,
        )
        self._specs[spec_id] = updated
        return updated

    def add_comment(
        self,
        spec_id: str,
        section_id: str,
        author: str,
        content: str,
    ) -> SpecComment:
        """Add a comment to a spec section."""
        self._get_spec(spec_id)
        comment = SpecComment(
            comment_id=uuid.uuid4().hex,
            spec_id=spec_id,
            section_id=section_id,
            author=author,
            content=content,
        )
        self._comments[spec_id].append(comment)
        return comment

    def resolve_comment(self, spec_id: str, comment_id: str) -> SpecComment:
        """Mark a comment as resolved."""
        self._get_spec(spec_id)
        comments = self._comments[spec_id]
        for i, c in enumerate(comments):
            if c.comment_id == comment_id:
                resolved = SpecComment(
                    comment_id=c.comment_id,
                    spec_id=c.spec_id,
                    section_id=c.section_id,
                    author=c.author,
                    content=c.content,
                    resolved=True,
                    created_at=c.created_at,
                )
                comments[i] = resolved
                return resolved
        msg = f"Comment {comment_id} not found in spec {spec_id}"
        raise KeyError(msg)

    def get_spec(self, spec_id: str) -> Spec:
        """Get a spec by ID. Raises KeyError if not found."""
        return self._get_spec(spec_id)

    def list_specs(self, status_filter: SpecStatus | None = None) -> list[Spec]:
        """List all specs, optionally filtered by status."""
        if status_filter is None:
            return list(self._specs.values())
        return [s for s in self._specs.values() if s.status == status_filter]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_spec(self, spec_id: str) -> Spec:
        """Look up a spec, raising KeyError if missing."""
        try:
            return self._specs[spec_id]
        except KeyError:
            msg = f"Spec {spec_id} not found"
            raise KeyError(msg) from None


def _replace_spec(spec: Spec, **overrides: object) -> Spec:
    """Return a new Spec with the given field overrides and bumped updated_at."""
    data: dict[str, object] = {
        "spec_id": spec.spec_id,
        "title": spec.title,
        "sections": spec.sections,
        "status": spec.status,
        "created_by": spec.created_by,
        "reviewers": spec.reviewers,
        "created_at": spec.created_at,
        "updated_at": datetime.now(tz=UTC),
        "version": spec.version,
    }
    data.update(overrides)
    return Spec(**data)  # type: ignore[arg-type]
