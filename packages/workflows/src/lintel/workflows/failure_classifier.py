"""Pipeline failure classifier for auto-improvement loop.

Categorises pipeline failures from stage logs into root cause classes
so that improvement changes can target failure CLASSES rather than
individual tasks (anti-overfitting rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re


class FailureClass(StrEnum):
    """Root cause categories for pipeline failures."""

    SANDBOX = "sandbox"
    TEST_FAILURE = "test_failure"
    PR_CREATION = "pr_creation"
    TIMEOUT = "timeout"
    AUTH = "auth"
    SILENT_FAILURE = "silent_failure"
    UNKNOWN = "unknown"


# Ordered list of (pattern, class) — first match wins.
_PATTERNS: list[tuple[re.Pattern[str], FailureClass]] = [
    # Sandbox / Docker errors
    (re.compile(r"sandbox.*(fail|error|crash|unavailable)", re.IGNORECASE), FailureClass.SANDBOX),
    (re.compile(r"docker.*(fail|error|timeout|not found)", re.IGNORECASE), FailureClass.SANDBOX),
    (re.compile(r"container.*(exit|kill|oom|crash)", re.IGNORECASE), FailureClass.SANDBOX),
    (re.compile(r"OOMKilled|out of memory", re.IGNORECASE), FailureClass.SANDBOX),
    # Test failures
    (
        re.compile(r"test.*fail|FAILED|AssertionError|pytest.*error", re.IGNORECASE),
        FailureClass.TEST_FAILURE,
    ),
    (re.compile(r"(\d+)\s+failed", re.IGNORECASE), FailureClass.TEST_FAILURE),
    (
        re.compile(r"exit code [1-9].*test|test.*exit code [1-9]", re.IGNORECASE),
        FailureClass.TEST_FAILURE,
    ),
    # PR creation
    (
        re.compile(r"pr.*(fail|error|reject)|pull request.*(fail|error)", re.IGNORECASE),
        FailureClass.PR_CREATION,
    ),
    (
        re.compile(r"merge conflict|branch.*protect|push.*reject", re.IGNORECASE),
        FailureClass.PR_CREATION,
    ),
    (re.compile(r"gh pr create.*fail|git push.*fail", re.IGNORECASE), FailureClass.PR_CREATION),
    # Timeouts
    (
        re.compile(r"timeout|timed?\s*out|deadline.*(exceeded|expired)", re.IGNORECASE),
        FailureClass.TIMEOUT,
    ),
    (re.compile(r"execution.*exceeded|max.*duration", re.IGNORECASE), FailureClass.TIMEOUT),
    # Auth
    (
        re.compile(r"auth.*(fail|error|denied|expired)|unauthorized|403|401", re.IGNORECASE),
        FailureClass.AUTH,
    ),
    (
        re.compile(r"token.*(expired|invalid|revoked)|permission denied", re.IGNORECASE),
        FailureClass.AUTH,
    ),
    (re.compile(r"credentials?.*(invalid|missing|expired)", re.IGNORECASE), FailureClass.AUTH),
]


@dataclass(frozen=True)
class ClassifiedFailure:
    """A single classified pipeline failure."""

    failure_class: FailureClass
    stage_name: str = ""
    matched_pattern: str = ""
    log_snippet: str = ""


@dataclass(frozen=True)
class ClassificationResult:
    """Summary of failure classification for a pipeline run."""

    run_id: str
    failures: tuple[ClassifiedFailure, ...] = ()
    primary_class: FailureClass = FailureClass.UNKNOWN

    @property
    def class_distribution(self) -> dict[FailureClass, int]:
        """Count of failures by class."""
        dist: dict[FailureClass, int] = {}
        for f in self.failures:
            dist[f.failure_class] = dist.get(f.failure_class, 0) + 1
        return dist


@dataclass
class FailureClassifier:
    """Classifies pipeline stage failures into root cause categories.

    Uses regex pattern matching against stage logs and error messages
    to assign each failure to a :class:`FailureClass`.  When no pattern
    matches AND the stage has no logs/error at all, the failure is
    classified as ``SILENT_FAILURE``.
    """

    extra_patterns: list[tuple[re.Pattern[str], FailureClass]] = field(default_factory=list)

    def classify_log(self, log_text: str) -> FailureClass:
        """Classify a single log/error string into a failure class."""
        all_patterns = _PATTERNS + self.extra_patterns
        for pattern, failure_class in all_patterns:
            if pattern.search(log_text):
                return failure_class
        return FailureClass.UNKNOWN

    def classify_stage(
        self,
        stage_name: str,
        *,
        error: str = "",
        logs: tuple[str, ...] | list[str] = (),
    ) -> ClassifiedFailure:
        """Classify a single failed stage."""
        combined = "\n".join([error, *logs]).strip()
        if not combined:
            return ClassifiedFailure(
                failure_class=FailureClass.SILENT_FAILURE,
                stage_name=stage_name,
                matched_pattern="(no logs or error)",
                log_snippet="",
            )

        failure_class = self.classify_log(combined)
        # Find the first matching pattern for the snippet
        matched = ""
        all_patterns = _PATTERNS + self.extra_patterns
        for pattern, _fc in all_patterns:
            m = pattern.search(combined)
            if m:
                matched = m.group(0)
                break

        # Extract a snippet around the match
        snippet = combined[:200] if len(combined) > 200 else combined

        return ClassifiedFailure(
            failure_class=failure_class,
            stage_name=stage_name,
            matched_pattern=matched,
            log_snippet=snippet,
        )

    def classify_pipeline(
        self,
        run_id: str,
        failed_stages: list[dict[str, object]],
    ) -> ClassificationResult:
        """Classify all failed stages of a pipeline run.

        Each item in ``failed_stages`` should have keys:
        - ``name`` (str): stage name
        - ``error`` (str): error message
        - ``logs`` (list[str] | tuple[str, ...]): stage log lines
        """
        failures: list[ClassifiedFailure] = []
        for stage in failed_stages:
            name = str(stage.get("name", ""))
            error = str(stage.get("error", ""))
            raw_logs = stage.get("logs", ())
            logs: tuple[str, ...] | list[str] = (
                raw_logs
                if isinstance(raw_logs, (tuple, list))
                else (str(raw_logs),)
            )
            failures.append(self.classify_stage(name, error=error, logs=logs))

        # Primary class is the most frequent one
        if failures:
            dist: dict[FailureClass, int] = {}
            for f in failures:
                dist[f.failure_class] = dist.get(f.failure_class, 0) + 1
            primary = max(dist, key=lambda k: dist[k])
        else:
            primary = FailureClass.UNKNOWN

        return ClassificationResult(
            run_id=run_id,
            failures=tuple(failures),
            primary_class=primary,
        )
