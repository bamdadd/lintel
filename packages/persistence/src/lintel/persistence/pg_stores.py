"""Postgres-backed stores for all remaining API packages.

These replace InMemory stores when DATABASE_URL is configured, using the
generic ``entities`` JSONB table via PostgresDictStore / PostgresComplianceStore.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from lintel.persistence.dict_store import PostgresComplianceStore, PostgresDictStore

if TYPE_CHECKING:
    import asyncpg


# ---------------------------------------------------------------------------
# Drift Detection stores
# ---------------------------------------------------------------------------


class PostgresDriftRuleStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "drift_rule", "rule_id")


class PostgresDriftAlertStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "drift_alert", "alert_id")


class PostgresDriftScanStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "drift_scan", "scan_id")


# ---------------------------------------------------------------------------
# Coding Rules stores
# ---------------------------------------------------------------------------


class PostgresCodingRuleStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "coding_rule", "rule_id")

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(project_id=project_id)

    async def match(
        self,
        file_path: str,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        all_rules = await self.list_all()
        matched: list[dict[str, Any]] = []
        for rule in all_rules:
            patterns = rule.get("file_patterns", [])
            if (not patterns or any(file_path.endswith(p.lstrip("*")) for p in patterns)) and (
                language is None or rule.get("language", "") in ("", language)
            ):
                matched.append(rule)
        return matched


class PostgresRuleViolationStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "rule_violation", "violation_id")

    async def list_by_rule(self, rule_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(rule_id=rule_id)

    async def list_by_pipeline(self, pipeline_run_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(pipeline_run_id=pipeline_run_id)


# ---------------------------------------------------------------------------
# Agent Skills stores
# ---------------------------------------------------------------------------


class PostgresAgentSkillStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "agent_skill", "skill_id")


class PostgresAgentSkillBindingStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "agent_skill_binding", "binding_id")

    async def list_by_agent(self, agent_definition_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(agent_definition_id=agent_definition_id)


# ---------------------------------------------------------------------------
# Workflow Blueprints
# ---------------------------------------------------------------------------


class PostgresWorkflowBlueprintStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "workflow_blueprint", "blueprint_id")


# ---------------------------------------------------------------------------
# Visual Verification
# ---------------------------------------------------------------------------


class PostgresVisualVerificationStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "visual_verification", "verification_id")

    async def list_by_pipeline(self, pipeline_run_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(pipeline_run_id=pipeline_run_id)


# ---------------------------------------------------------------------------
# Privacy Controls
# ---------------------------------------------------------------------------


class PostgresVisibilityStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "metric_visibility", "visibility_id")


class PostgresPreferenceStore:
    """Postgres-backed privacy preference store (uses put, not add)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "privacy_preference")

    async def get(self, user_id: str) -> dict[str, Any] | None:
        return await self._store.get(user_id)

    async def put(self, item: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        user_id = data["user_id"]
        await self._store.put(user_id, data)
        return data


# ---------------------------------------------------------------------------
# AI Firewall stores
# ---------------------------------------------------------------------------


class PostgresFirewallRuleStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "firewall_rule", "rule_id")


class PostgresFirewallLogStore:
    """Postgres-backed firewall log store with filtered listing."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "firewall_log")

    async def add(self, entry: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entry) if hasattr(entry, "__dataclass_fields__") else dict(entry)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        entry_id = data.get("log_id", data.get("entry_id", ""))
        await self._store.put(entry_id, data)
        return data

    async def list_all(
        self,
        *,
        rule_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {}
        if rule_id is not None:
            filters["rule_id"] = rule_id
        if action is not None:
            filters["action"] = action
        results = await self._store.list_all(**filters)
        return results[:limit]


# ---------------------------------------------------------------------------
# Slack Notification stores
# ---------------------------------------------------------------------------


class PostgresSlackNotificationTemplateStore:
    """Postgres-backed slack notification template store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "slack_notification_template")

    async def add(self, item: Any) -> None:  # noqa: ANN401
        data = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["template_id"], data)

    async def get(self, template_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(template_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def update(self, item: Any) -> None:  # noqa: ANN401
        data = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["template_id"], data)

    async def remove(self, template_id: str) -> None:
        await self._store.remove(template_id)


class PostgresSlackNotificationRecordStore:
    """Postgres-backed slack notification record store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "slack_notification_record")

    async def add(self, item: Any) -> None:  # noqa: ANN401
        data = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["record_id"], data)

    async def get(self, record_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(record_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def list_by_pipeline(self, pipeline_run_id: str) -> list[Any]:
        return await self._store.list_all(pipeline_run_id=pipeline_run_id)

    async def list_by_stage(self, stage_name: str) -> list[Any]:
        return await self._store.list_all(stage_name=stage_name)


# ---------------------------------------------------------------------------
# Slack Workflow Invocations
# ---------------------------------------------------------------------------


class PostgresSlackInvocationStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "slack_invocation", "invocation_id")


# ---------------------------------------------------------------------------
# Sandbox Pool stores
# ---------------------------------------------------------------------------


class PostgresSandboxImageStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "sandbox_image", "image_id")


class PostgresPooledSandboxStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "pooled_sandbox", "sandbox_id")

    async def acquire_warm(self, project_id: str) -> dict[str, Any] | None:
        items = await self._store.list_all(
            project_id=project_id,
            status="warm",
        )
        if not items:
            return None
        # Mark the first warm sandbox as acquired
        item = items[0]
        item["status"] = "acquired"
        await self._store.put(item["sandbox_id"], item)
        return item


class PostgresSandboxPoolConfigStore:
    """Postgres-backed sandbox pool config store (uses upsert, not add)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "sandbox_pool_config")

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return await self._store.get(project_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._store.list_all()

    async def list_configs(self) -> list[Any]:
        return await self._store.list_all()

    async def upsert(self, config: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(config) if hasattr(config, "__dataclass_fields__") else dict(config)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        project_id = data["project_id"]
        await self._store.put(project_id, data)
        return data


class PostgresImageRebuildStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "image_rebuild", "rebuild_id")

    async def latest_for_project(self, project_id: str) -> dict[str, Any] | None:
        items = await self._store.list_all(project_id=project_id)
        return items[-1] if items else None

    async def list_by_image(self, image_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(image_id=image_id)


# ---------------------------------------------------------------------------
# Sandbox Snapshots
# ---------------------------------------------------------------------------


class PostgresSnapshotStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "sandbox_snapshot", "snapshot_id")

    async def list_by_sandbox(self, sandbox_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(sandbox_id=sandbox_id)


# ---------------------------------------------------------------------------
# Sandbox Credentials
# ---------------------------------------------------------------------------


class PostgresSandboxCredentialStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "sandbox_credential", "credential_id")

    async def list_by_sandbox(self, sandbox_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(sandbox_id=sandbox_id)

    async def revoke_all_for_sandbox(self, sandbox_id: str) -> int:
        items = await self.list_by_sandbox(sandbox_id)
        count = 0
        for item in items:
            cid = item.get("credential_id", "")
            if cid:
                await self.remove(cid)
                count += 1
        return count


# ---------------------------------------------------------------------------
# Channel Connections
# ---------------------------------------------------------------------------


class PostgresChannelConnectionStore:
    """Postgres-backed channel connection store (returns dataclass-like dicts)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "channel_connection")

    async def add(self, connection: Any) -> None:  # noqa: ANN401
        data = (
            asdict(connection) if hasattr(connection, "__dataclass_fields__") else dict(connection)
        )
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["connection_id"], data)

    async def get(self, connection_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(connection_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def update(self, connection: Any) -> None:  # noqa: ANN401
        data = (
            asdict(connection) if hasattr(connection, "__dataclass_fields__") else dict(connection)
        )
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["connection_id"], data)

    async def remove(self, connection_id: str) -> None:
        await self._store.remove(connection_id)


# ---------------------------------------------------------------------------
# Digest stores
# ---------------------------------------------------------------------------


class PostgresDigestStore:
    """Postgres-backed digest store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "digest")

    async def add(self, digest: Any) -> None:  # noqa: ANN401
        data = asdict(digest) if hasattr(digest, "__dataclass_fields__") else dict(digest)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["digest_id"], data)

    async def get(self, digest_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(digest_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def remove(self, digest_id: str) -> None:
        await self._store.remove(digest_id)


class PostgresDigestConfigStore:
    """Postgres-backed digest config store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "digest_config")

    async def add(self, config: Any) -> None:  # noqa: ANN401
        data = asdict(config) if hasattr(config, "__dataclass_fields__") else dict(config)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["config_id"], data)

    async def get(self, config_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(config_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def update(self, config: Any) -> None:  # noqa: ANN401
        data = asdict(config) if hasattr(config, "__dataclass_fields__") else dict(config)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["config_id"], data)

    async def remove(self, config_id: str) -> None:
        await self._store.remove(config_id)


# ---------------------------------------------------------------------------
# Release Notes
# ---------------------------------------------------------------------------


class PostgresReleaseNoteStore:
    """Postgres-backed release note store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "release_note")

    async def add(self, note: Any) -> None:  # noqa: ANN401
        data = asdict(note) if hasattr(note, "__dataclass_fields__") else dict(note)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["note_id"], data)

    async def get(self, note_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(note_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def list_by_project(self, project_id: str) -> list[Any]:
        return await self._store.list_all(project_id=project_id)

    async def update(self, note: Any) -> None:  # noqa: ANN401
        data = asdict(note) if hasattr(note, "__dataclass_fields__") else dict(note)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["note_id"], data)

    async def remove(self, note_id: str) -> None:
        await self._store.remove(note_id)


# ---------------------------------------------------------------------------
# Scheduled Tasks
# ---------------------------------------------------------------------------


class PostgresScheduledTaskStore:
    """Postgres-backed scheduled task store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "scheduled_task")

    async def add(self, task: Any) -> None:  # noqa: ANN401
        data = asdict(task) if hasattr(task, "__dataclass_fields__") else dict(task)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["task_id"], data)

    async def get(self, task_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(task_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def list_by_project(self, project_id: str) -> list[Any]:
        return await self._store.list_all(project_id=project_id)

    async def update(self, task: Any) -> None:  # noqa: ANN401
        data = asdict(task) if hasattr(task, "__dataclass_fields__") else dict(task)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["task_id"], data)

    async def remove(self, task_id: str) -> None:
        await self._store.remove(task_id)


# ---------------------------------------------------------------------------
# Codebase Index store
# ---------------------------------------------------------------------------


class PostgresCodebaseIndexStore:
    """Postgres-backed codebase index store with two collections."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._indices = PostgresDictStore(pool, "codebase_index")
        self._entries = PostgresDictStore(pool, "codebase_entry")

    # --- Index CRUD ---

    async def add_index(self, data: dict[str, Any]) -> dict[str, Any]:
        await self._indices.put(data["index_id"], data)
        return data

    async def get_index(self, index_id: str) -> dict[str, Any] | None:
        return await self._indices.get(index_id)

    async def list_indices(self) -> list[dict[str, Any]]:
        return await self._indices.list_all()

    async def list_indices_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return await self._indices.list_all(project_id=project_id)

    async def update_index(self, index_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self._indices.get(index_id)
        if existing is None:
            return None
        merged = {**existing, **data}
        await self._indices.put(index_id, merged)
        return merged

    async def remove_index(self, index_id: str) -> bool:
        # Remove associated entries first
        entries = await self.list_entries_by_index(index_id)
        for entry in entries:
            await self._entries.remove(entry["entry_id"])
        return await self._indices.remove(index_id)

    # --- Entry CRUD ---

    async def add_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        await self._entries.put(data["entry_id"], data)
        return data

    async def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        return await self._entries.get(entry_id)

    async def list_entries_by_index(self, index_id: str) -> list[dict[str, Any]]:
        return await self._entries.list_all(index_id=index_id)

    # --- Search ---

    async def search(self, index_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Naive keyword search — real implementation would use vector similarity."""
        entries = await self.list_entries_by_index(index_id)
        results: list[dict[str, Any]] = []
        q_lower = query.lower()
        for entry in entries:
            content = entry.get("content", "").lower()
            if q_lower in content:
                results.append(
                    {
                        "entry_id": entry["entry_id"],
                        "index_id": entry["index_id"],
                        "file_path": entry.get("file_path", ""),
                        "content": entry.get("content", ""),
                        "score": 1.0,
                        "language": entry.get("language", ""),
                        "start_line": entry.get("start_line", 0),
                        "end_line": entry.get("end_line", 0),
                    }
                )
            if len(results) >= limit:
                break
        return results


# ---------------------------------------------------------------------------
# Trust Score store
# ---------------------------------------------------------------------------


class PostgresTrustScoreStore:
    """Postgres-backed trust score store with history sub-collection."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._scores = PostgresDictStore(pool, "trust_score")
        self._history = PostgresDictStore(pool, "trust_history")
        self._history_counter = 0

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        return await self._scores.get(agent_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._scores.list_all()

    async def add(self, trust_score: Any) -> dict[str, Any]:  # noqa: ANN401
        data = (
            asdict(trust_score)
            if hasattr(trust_score, "__dataclass_fields__")
            else dict(trust_score)
        )
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
            elif hasattr(v, "isoformat"):
                data[k] = v.isoformat()
        agent_id = data["agent_id"]
        await self._scores.put(agent_id, data)
        return data

    async def update(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self._scores.get(agent_id)
        if existing is None:
            return None
        existing.update(updates)
        await self._scores.put(agent_id, existing)
        return existing

    async def remove(self, agent_id: str) -> bool:
        # Remove history too
        history = await self.get_history(agent_id)
        for h in history:
            hid = h.get("_history_id", "")
            if hid:
                await self._history.remove(hid)
        return await self._scores.remove(agent_id)

    async def add_history(self, entry: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entry) if hasattr(entry, "__dataclass_fields__") else dict(entry)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
            elif hasattr(v, "isoformat"):
                data[k] = v.isoformat()
            elif isinstance(v, dict):
                for dk, dv in v.items():
                    if hasattr(dv, "isoformat"):
                        v[dk] = dv.isoformat()
        self._history_counter += 1
        history_id = f"{data['agent_id']}_{self._history_counter}"
        data["_history_id"] = history_id
        await self._history.put(history_id, data)
        return data

    async def get_history(self, agent_id: str) -> list[dict[str, Any]]:
        return await self._history.list_all(agent_id=agent_id)


# ---------------------------------------------------------------------------
# Context Attachments
# ---------------------------------------------------------------------------


class PostgresAttachmentStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "context_attachment", "attachment_id")

    async def list_by_target(self, target_type: str, target_id: str) -> list[dict[str, Any]]:
        all_items = await self.list_all()
        return [
            item
            for item in all_items
            if item.get("target_type") == target_type and item.get("target_id") == target_id
        ]


# ---------------------------------------------------------------------------
# Artifacts: Parsed Test Results, Coverage Metrics, Quality Gate Rules
# ---------------------------------------------------------------------------


class PostgresParsedTestResultStore:
    """Postgres-backed parsed test result store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "parsed_test_result")

    async def save(
        self,
        result_id: str,
        run_id: str,
        project_id: str,
        artifact_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "result_id": result_id,
            "run_id": run_id,
            "project_id": project_id,
            "artifact_id": artifact_id,
            **data,
        }
        await self._store.put(result_id, record)
        return record

    async def get_by_run(self, run_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(run_id=run_id)

    async def get(self, result_id: str) -> dict[str, Any] | None:
        return await self._store.get(result_id)


class PostgresCoverageMetricStore:
    """Postgres-backed coverage metric store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "coverage_metric")

    async def save(
        self,
        metric_id: str,
        run_id: str,
        project_id: str,
        artifact_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "metric_id": metric_id,
            "run_id": run_id,
            "project_id": project_id,
            "artifact_id": artifact_id,
            **data,
        }
        await self._store.put(metric_id, record)
        return record

    async def get_by_run(self, run_id: str) -> dict[str, Any] | None:
        results = await self._store.list_all(run_id=run_id)
        return results[0] if results else None

    async def get_latest_by_project(
        self,
        project_id: str,
    ) -> dict[str, Any] | None:
        results = await self._store.list_all(project_id=project_id)
        return results[-1] if results else None


class PostgresQualityGateRuleStore(PostgresComplianceStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool, "quality_gate_rule", "rule_id")


# ---------------------------------------------------------------------------
# MCP Tool stores
# ---------------------------------------------------------------------------


class PostgresMCPToolStore:
    """Postgres-backed MCP tool store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "mcp_tool")

    async def add(self, tool: Any) -> None:  # noqa: ANN401
        data = asdict(tool) if hasattr(tool, "__dataclass_fields__") else dict(tool)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["tool_id"], data)

    async def get(self, tool_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(tool_id)

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def list_by_server(self, server_id: str) -> list[Any]:
        return await self._store.list_all(server_id=server_id)

    async def list_by_classification(self, classification: str) -> list[Any]:
        return await self._store.list_all(classification=classification)

    async def remove(self, tool_id: str) -> bool:
        return await self._store.remove(tool_id)


class PostgresMCPToolAllowlistStore:
    """Postgres-backed MCP tool allowlist store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "mcp_tool_allowlist")

    async def set(self, allowlist: Any) -> None:  # noqa: ANN401
        data = asdict(allowlist) if hasattr(allowlist, "__dataclass_fields__") else dict(allowlist)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        await self._store.put(data["allowlist_id"], data)

    async def get(self, allowlist_id: str) -> Any:  # noqa: ANN401
        return await self._store.get(allowlist_id)

    async def get_by_project(self, project_id: str) -> Any:  # noqa: ANN401
        results = await self._store.list_all(project_id=project_id)
        return results[0] if results else None

    async def list_all(self) -> list[Any]:
        return await self._store.list_all()

    async def remove(self, allowlist_id: str) -> bool:
        return await self._store.remove(allowlist_id)
