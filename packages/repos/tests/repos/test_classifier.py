"""Tests for the repository auto-classifier."""

from __future__ import annotations

from lintel.repos.classifier import RepoClassifier, _extract_url_parts
from lintel.repos.types import Repository


def _make_repo(
    name: str,
    url: str = "",
    owner: str = "",
    repo_id: str = "",
) -> Repository:
    return Repository(
        repo_id=repo_id or name,
        name=name,
        url=url or f"https://github.com/{owner or 'org'}/{name}",
        owner=owner,
    )


class TestRepoClassifier:
    def test_exact_name_match(self) -> None:
        repos = [_make_repo("lintel"), _make_repo("other-project")]
        classifier = RepoClassifier()
        results = classifier.classify("fix the bug in lintel", repos)
        assert len(results) >= 1
        assert results[0].repo_id == "lintel"
        assert results[0].confidence >= 0.5

    def test_no_match_returns_empty(self) -> None:
        repos = [_make_repo("lintel")]
        classifier = RepoClassifier()
        results = classifier.classify("what is the weather today?", repos)
        assert results == []

    def test_owner_match(self) -> None:
        repos = [_make_repo("api", owner="acme"), _make_repo("api", owner="initech")]
        classifier = RepoClassifier()
        results = classifier.classify("the acme api needs a fix", repos)
        assert len(results) >= 1
        top = results[0]
        assert top.repo_name == "api"
        assert "acme" in [k.lower() for k in top.matched_keywords]

    def test_url_component_match(self) -> None:
        repos = [_make_repo("app", url="https://github.com/stripe/app")]
        classifier = RepoClassifier()
        results = classifier.classify("the stripe service is broken", repos)
        assert len(results) == 1
        assert results[0].confidence > 0

    def test_token_overlap_partial_match(self) -> None:
        repos = [_make_repo("payment-gateway")]
        classifier = RepoClassifier()
        results = classifier.classify("the payment system is slow", repos)
        assert len(results) == 1
        assert results[0].confidence > 0
        assert "payment" in results[0].matched_keywords

    def test_results_sorted_by_confidence(self) -> None:
        repos = [
            _make_repo("unrelated", owner="nobody"),
            _make_repo("lintel", owner="bamdadd"),
        ]
        classifier = RepoClassifier()
        results = classifier.classify("update lintel by bamdadd", repos)
        assert len(results) >= 1
        assert results[0].repo_id == "lintel"
        # Confidence should be descending
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i + 1].confidence

    def test_confidence_capped_at_1(self) -> None:
        repos = [_make_repo("lintel", owner="lintel", url="https://github.com/lintel/lintel")]
        classifier = RepoClassifier()
        results = classifier.classify("lintel lintel lintel", repos)
        assert results[0].confidence <= 1.0

    def test_reason_populated(self) -> None:
        repos = [_make_repo("my-project")]
        classifier = RepoClassifier()
        results = classifier.classify("fix my-project", repos)
        assert results[0].reason != ""

    def test_caching(self) -> None:
        repos = [_make_repo("lintel")]
        classifier = RepoClassifier(cache_ttl_seconds=60.0)
        r1 = classifier.classify("fix lintel", repos)
        r2 = classifier.classify("fix lintel", repos)
        assert r1 == r2

    def test_clear_cache(self) -> None:
        repos = [_make_repo("lintel")]
        classifier = RepoClassifier()
        classifier.classify("fix lintel", repos)
        classifier.clear_cache()
        # Should still work after cache clear
        results = classifier.classify("fix lintel", repos)
        assert len(results) == 1

    def test_empty_repositories(self) -> None:
        classifier = RepoClassifier()
        results = classifier.classify("fix everything", [])
        assert results == []


class TestExtractUrlParts:
    def test_https_github_url(self) -> None:
        parts = _extract_url_parts("https://github.com/acme/my-service.git")
        assert "acme" in parts
        assert "my-service" in parts

    def test_trailing_slash(self) -> None:
        parts = _extract_url_parts("https://github.com/org/repo/")
        assert "org" in parts
        assert "repo" in parts

    def test_plain_url(self) -> None:
        parts = _extract_url_parts("https://github.com/foo/bar")
        assert "foo" in parts
        assert "bar" in parts

    def test_github_host_excluded(self) -> None:
        parts = _extract_url_parts("https://github.com/org/repo")
        assert "github.com" not in parts
