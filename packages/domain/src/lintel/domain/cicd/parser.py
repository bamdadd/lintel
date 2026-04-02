"""CI webhook payload parser — normalizes provider payloads into CIBuild."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.cicd.types import CIBuild, CIBuildStatus, CIProvider, CIWebhookPayload


class CIWebhookParser:
    """Parses raw CI webhook payloads into normalized CIBuild instances."""

    def parse(self, payload: CIWebhookPayload) -> CIBuild:
        """Dispatch to the correct provider parser."""
        if payload.provider == CIProvider.GITHUB_ACTIONS:
            return self._parse_github_actions(payload)
        if payload.provider == CIProvider.CONCOURSE:
            return self._parse_concourse(payload)
        return self._parse_generic(payload)

    def _parse_github_actions(self, payload: CIWebhookPayload) -> CIBuild:
        body = payload.body
        workflow_run = body.get("workflow_run", body)
        if not isinstance(workflow_run, dict):
            workflow_run = {}

        head_commit = workflow_run.get("head_commit", {})
        if not isinstance(head_commit, dict):
            head_commit = {}

        repo = workflow_run.get("repository", workflow_run.get("head_repository", {}))
        if not isinstance(repo, dict):
            repo = {}

        return CIBuild(
            build_id=str(workflow_run.get("id", "")),
            provider=CIProvider.GITHUB_ACTIONS,
            status=self._map_github_status(
                str(workflow_run.get("status", "")),
                str(workflow_run.get("conclusion", "")),
            ),
            repo_url=str(repo.get("html_url", "")),
            branch=str(workflow_run.get("head_branch", "")),
            commit_sha=str(workflow_run.get("head_sha", head_commit.get("id", ""))),
            pipeline_name=str(workflow_run.get("name", "")),
            build_url=str(workflow_run.get("html_url", "")),
            started_at=_parse_iso(workflow_run.get("run_started_at")),
            finished_at=_parse_iso(workflow_run.get("updated_at")),
        )

    def _parse_concourse(self, payload: CIWebhookPayload) -> CIBuild:
        body = payload.body
        return CIBuild(
            build_id=str(body.get("build_id", "")),
            provider=CIProvider.CONCOURSE,
            status=self._map_concourse_status(str(body.get("status", ""))),
            repo_url=str(body.get("repo_url", "")),
            branch=str(body.get("branch", "")),
            commit_sha=str(body.get("commit_sha", "")),
            pipeline_name=str(body.get("pipeline_name", "")),
            build_url=str(body.get("build_url", "")),
            started_at=_parse_iso(body.get("started_at")),
            finished_at=_parse_iso(body.get("finished_at")),
        )

    def _parse_generic(self, payload: CIWebhookPayload) -> CIBuild:
        body = payload.body
        raw_status = str(body.get("status", "unknown"))
        return CIBuild(
            build_id=str(body.get("build_id", "")),
            provider=payload.provider,
            status=CIBuildStatus(raw_status)
            if raw_status in CIBuildStatus.__members__.values()
            else CIBuildStatus.UNKNOWN,
            repo_url=str(body.get("repo_url", "")),
            branch=str(body.get("branch", "")),
            commit_sha=str(body.get("commit_sha", "")),
            pipeline_name=str(body.get("pipeline_name", "")),
            build_url=str(body.get("build_url", "")),
            started_at=_parse_iso(body.get("started_at")),
            finished_at=_parse_iso(body.get("finished_at")),
        )

    @staticmethod
    def _map_github_status(status: str, conclusion: str) -> CIBuildStatus:
        if status == "queued":
            return CIBuildStatus.PENDING
        if status == "in_progress":
            return CIBuildStatus.RUNNING
        if status == "completed":
            conclusion_map: dict[str, CIBuildStatus] = {
                "success": CIBuildStatus.SUCCESS,
                "failure": CIBuildStatus.FAILURE,
                "cancelled": CIBuildStatus.CANCELLED,
            }
            return conclusion_map.get(conclusion, CIBuildStatus.UNKNOWN)
        return CIBuildStatus.UNKNOWN

    @staticmethod
    def _map_concourse_status(status: str) -> CIBuildStatus:
        mapping: dict[str, CIBuildStatus] = {
            "started": CIBuildStatus.RUNNING,
            "succeeded": CIBuildStatus.SUCCESS,
            "failed": CIBuildStatus.FAILURE,
            "aborted": CIBuildStatus.CANCELLED,
            "pending": CIBuildStatus.PENDING,
        }
        return mapping.get(status, CIBuildStatus.UNKNOWN)


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(UTC)
    except ValueError:
        return None
