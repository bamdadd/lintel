"""Tests for RepoSelector engine."""

from __future__ import annotations

from lintel.workflow_repo_selector_api.selector import RepoSelector
from lintel.workflow_repo_selector_api.store import RepoDescription


def _make_repo(**kwargs: object) -> RepoDescription:
    return RepoDescription(**kwargs)  # type: ignore[arg-type]


class TestRepoSelector:
    def setup_method(self) -> None:
        self.selector = RepoSelector()

    def test_no_repos_returns_empty(self) -> None:
        result = self.selector.select([], "some description", "")
        assert result == []

    def test_matching_by_description_keywords(self) -> None:
        repo = _make_repo(
            repo_id="r1",
            name="backend",
            description="REST API service",
        )
        result = self.selector.select([repo], "fix REST endpoint", "")
        assert len(result) == 1
        assert result[0].repo_id == "r1"

    def test_higher_overlap_scores_higher(self) -> None:
        low = _make_repo(repo_id="low", name="low", description="API")
        high = _make_repo(repo_id="high", name="high", description="API REST service")
        result = self.selector.select([low, high], "API REST service call", "")
        assert len(result) == 2
        assert result[0].repo_id == "high"
        assert result[0].score > result[1].score

    def test_project_id_filtering(self) -> None:
        r1 = _make_repo(repo_id="r1", name="a", project_id="p1", description="shared code")
        r2 = _make_repo(repo_id="r2", name="b", project_id="p2", description="shared code")
        result = self.selector.select([r1, r2], "shared", "p1")
        assert len(result) == 1
        assert result[0].repo_id == "r1"

    def test_tags_and_languages_contribute(self) -> None:
        repo = _make_repo(
            repo_id="r1",
            name="svc",
            description="",
            tags=["python"],
            languages=["typescript"],
        )
        result = self.selector.select([repo], "python typescript project", "")
        assert len(result) == 1
        assert result[0].score > 0
