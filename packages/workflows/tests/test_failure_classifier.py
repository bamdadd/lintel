"""Tests for the pipeline failure classifier."""

import pytest

from lintel.workflows.failure_classifier import (
    FailureClass,
    FailureClassifier,
)


@pytest.fixture()
def classifier() -> FailureClassifier:
    return FailureClassifier()


class TestClassifyLog:
    def test_sandbox_docker_error(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("docker container failed to start") == FailureClass.SANDBOX

    def test_sandbox_oom(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("container OOMKilled after 2GB") == FailureClass.SANDBOX

    def test_sandbox_error(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("sandbox unavailable") == FailureClass.SANDBOX

    def test_test_failure_pytest(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("3 failed, 10 passed") == FailureClass.TEST_FAILURE

    def test_test_failure_assertion(self, classifier: FailureClassifier) -> None:
        assert (
            classifier.classify_log("AssertionError: expected 5 got 3") == FailureClass.TEST_FAILURE
        )

    def test_pr_creation_push_rejected(self, classifier: FailureClassifier) -> None:
        assert (
            classifier.classify_log("push rejected by branch protection")
            == FailureClass.PR_CREATION
        )

    def test_pr_creation_merge_conflict(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("merge conflict in src/main.py") == FailureClass.PR_CREATION

    def test_timeout(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("execution timed out after 3600s") == FailureClass.TIMEOUT

    def test_timeout_deadline(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("deadline exceeded") == FailureClass.TIMEOUT

    def test_auth_unauthorized(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("401 Unauthorized") == FailureClass.AUTH

    def test_auth_token_expired(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("token expired") == FailureClass.AUTH

    def test_auth_permission_denied(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("permission denied for resource") == FailureClass.AUTH

    def test_unknown_unrecognised(self, classifier: FailureClassifier) -> None:
        assert classifier.classify_log("something weird happened") == FailureClass.UNKNOWN


class TestClassifyStage:
    def test_silent_failure_no_logs(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_stage("build", error="", logs=())
        assert result.failure_class == FailureClass.SILENT_FAILURE
        assert result.stage_name == "build"

    def test_stage_with_error(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_stage("test", error="3 failed, 2 passed")
        assert result.failure_class == FailureClass.TEST_FAILURE
        assert result.stage_name == "test"

    def test_stage_with_logs(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_stage(
            "deploy",
            logs=("Deploying...", "docker container failed to start"),
        )
        assert result.failure_class == FailureClass.SANDBOX

    def test_snippet_truncated(self, classifier: FailureClassifier) -> None:
        long_log = "x" * 300 + " docker error"
        result = classifier.classify_stage("deploy", error=long_log)
        assert len(result.log_snippet) <= 200


class TestClassifyPipeline:
    def test_empty_stages(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_pipeline("run-1", [])
        assert result.run_id == "run-1"
        assert result.primary_class == FailureClass.UNKNOWN
        assert result.failures == ()

    def test_single_failure(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_pipeline(
            "run-2",
            [{"name": "test", "error": "5 failed", "logs": []}],
        )
        assert result.primary_class == FailureClass.TEST_FAILURE
        assert len(result.failures) == 1

    def test_multiple_failures_picks_dominant(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_pipeline(
            "run-3",
            [
                {"name": "test-1", "error": "3 failed", "logs": []},
                {"name": "test-2", "error": "2 failed", "logs": []},
                {"name": "deploy", "error": "timeout exceeded", "logs": []},
            ],
        )
        assert result.primary_class == FailureClass.TEST_FAILURE
        assert result.class_distribution[FailureClass.TEST_FAILURE] == 2
        assert result.class_distribution[FailureClass.TIMEOUT] == 1

    def test_class_distribution_property(self, classifier: FailureClassifier) -> None:
        result = classifier.classify_pipeline(
            "run-4",
            [
                {"name": "a", "error": "sandbox failed", "logs": []},
                {"name": "b", "error": "sandbox error", "logs": []},
                {"name": "c", "error": "token expired", "logs": []},
            ],
        )
        dist = result.class_distribution
        assert dist[FailureClass.SANDBOX] == 2
        assert dist[FailureClass.AUTH] == 1


class TestExtraPatterns:
    def test_custom_pattern(self) -> None:
        import re

        classifier = FailureClassifier(
            extra_patterns=[(re.compile(r"custom_err_\d+"), FailureClass.SANDBOX)],
        )
        assert classifier.classify_log("custom_err_42 happened") == FailureClass.SANDBOX
