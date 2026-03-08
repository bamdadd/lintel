"""Typed Postgres-backed stores for entities with custom methods."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.infrastructure.persistence.crud_store import PostgresCrudStore
from lintel.infrastructure.persistence.dict_store import PostgresDictStore

if TYPE_CHECKING:
    import asyncpg

    from lintel.contracts.types import (
        AIProvider,
        Credential,
        Repository,
        SkillDescriptor,
    )


class PostgresRepositoryStore(PostgresCrudStore):
    """Repository store with get_by_url support."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Repository

        super().__init__(pool, "repository", "repo_id", Repository)

    async def get_by_url(self, url: str) -> Repository | None:
        results = await self.list_all(url=url)
        return results[0] if results else None


class PostgresAIProviderStore(PostgresCrudStore):
    """AI provider store with API key management."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import AIProvider

        super().__init__(pool, "ai_provider", "provider_id", AIProvider)
        self._pool_ref = pool

    async def add(self, provider: Any, api_key: str = "") -> None:  # noqa: ANN401
        await super().add(provider)
        if api_key:
            await self.update_api_key(provider.provider_id, api_key)

    async def update_api_key(self, provider_id: str, api_key: str) -> None:
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ('ai_provider_key', $1, $2::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $2::jsonb, updated_at = now()
                """,
                provider_id,
                json.dumps({"api_key": api_key}),
            )

    async def has_api_key(self, provider_id: str) -> bool:
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT 1 FROM entities WHERE kind = 'ai_provider_key' AND entity_id = $1",
                provider_id,
            )
            return row is not None

    async def get_default(self) -> AIProvider | None:
        results = await self.list_all(is_default="true")
        return results[0] if results else None

    async def remove(self, provider_id: str) -> None:
        await super().remove(provider_id)
        # Also remove the API key
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                "DELETE FROM entities WHERE kind = 'ai_provider_key' AND entity_id = $1",
                provider_id,
            )


class PostgresMCPServerStore(PostgresCrudStore):
    """MCP server store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import MCPServer

        super().__init__(pool, "mcp_server", "server_id", MCPServer)

    async def list_enabled(self) -> list[Any]:
        return await self.list_all(enabled="true")


class PostgresCredentialStore(PostgresCrudStore):
    """Credential store with secret management."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Credential

        super().__init__(pool, "credential", "credential_id", Credential)
        self._pool_ref = pool

    async def store(
        self,
        credential_id: str,
        credential_type: str,
        name: str,
        secret: str,
        repo_ids: list[str] | None = None,
    ) -> Credential:
        from lintel.contracts.types import Credential, CredentialType

        cred = Credential(
            credential_id=credential_id,
            credential_type=CredentialType(credential_type),
            name=name,
            repo_ids=frozenset(repo_ids) if repo_ids else frozenset(),
        )
        await self.add(cred)
        # Store secret separately
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ('credential_secret', $1, $2::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $2::jsonb, updated_at = now()
                """,
                credential_id,
                json.dumps({"secret": secret}),
            )
        return cred

    async def get_secret(self, credential_id: str) -> str | None:
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = 'credential_secret' AND entity_id = $1",
                credential_id,
            )
        if row is None:
            return None
        data = json.loads(row["data"])
        return data.get("secret")  # type: ignore[no-any-return]

    async def list_by_repo(self, repo_id: str) -> list[Credential]:
        all_creds = await self.list_all()
        return [c for c in all_creds if not c.repo_ids or repo_id in c.repo_ids]

    async def revoke(self, credential_id: str) -> None:
        await self.remove(credential_id)
        async with self._pool_ref.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                "DELETE FROM entities WHERE kind = 'credential_secret' AND entity_id = $1",
                credential_id,
            )


class PostgresPolicyStore(PostgresCrudStore):
    """Policy store with list_by_project."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Policy

        super().__init__(pool, "policy", "policy_id", Policy)

    async def list_by_project(self, project_id: str) -> list[Any]:
        return await self.list_all(project_id=project_id)


class PostgresEnvironmentStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Environment

        super().__init__(pool, "environment", "environment_id", Environment)


class PostgresTeamStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Team

        super().__init__(pool, "team", "team_id", Team)


class PostgresUserStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import User

        super().__init__(pool, "user", "user_id", User)


class PostgresTriggerStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Trigger

        super().__init__(pool, "trigger", "trigger_id", Trigger)


class PostgresVariableStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Variable

        super().__init__(pool, "variable", "variable_id", Variable)


class PostgresPipelineStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import PipelineRun

        super().__init__(pool, "pipeline_run", "run_id", PipelineRun)


class PostgresApprovalRequestStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import ApprovalRequest

        super().__init__(pool, "approval_request", "approval_id", ApprovalRequest)


class PostgresNotificationRuleStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import NotificationRule

        super().__init__(pool, "notification_rule", "rule_id", NotificationRule)


class PostgresAuditEntryStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import AuditEntry

        super().__init__(pool, "audit_entry", "entry_id", AuditEntry)


class PostgresCodeArtifactStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import CodeArtifact

        super().__init__(pool, "code_artifact", "artifact_id", CodeArtifact)


class PostgresTestResultStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import TestResult

        super().__init__(pool, "test_result", "result_id", TestResult)


class PostgresProjectStore:
    """Postgres-backed project store (dict-based interface)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "project")

    async def add(self, project: Any) -> None:  # noqa: ANN401
        data = asdict(project)
        await self._store.put(data["project_id"], data)

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return await self._store.get(project_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._store.list_all()

    async def update(self, project_id: str, data: dict[str, Any]) -> None:
        await self._store.put(project_id, data)

    async def remove(self, project_id: str) -> None:
        await self._store.remove(project_id)


class PostgresWorkItemStore:
    """Postgres-backed work item store (dict-based interface)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "work_item")

    async def add(self, work_item: Any) -> None:  # noqa: ANN401
        data = asdict(work_item)
        await self._store.put(data["work_item_id"], data)

    async def get(self, work_item_id: str) -> dict[str, Any] | None:
        return await self._store.get(work_item_id)

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id is not None:
            return await self._store.list_all(project_id=project_id)
        return await self._store.list_all()

    async def update(self, work_item_id: str, data: dict[str, Any]) -> None:
        await self._store.put(work_item_id, data)

    async def remove(self, work_item_id: str) -> None:
        await self._store.remove(work_item_id)


class PostgresChatStore:
    """Postgres-backed chat store (async methods)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "conversation")

    async def create(
        self,
        *,
        conversation_id: str,
        user_id: str,
        display_name: str | None,
        project_id: str | None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        from lintel.contracts.data_models import ConversationData

        conv = ConversationData(
            conversation_id=conversation_id,
            user_id=user_id,
            display_name=display_name,
            project_id=project_id,
            model_id=model_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        data = conv.model_dump()
        await self._store.put(conversation_id, data)
        return data

    async def get(self, conversation_id: str) -> dict[str, Any] | None:
        return await self._store.get(conversation_id)

    async def delete(self, conversation_id: str) -> bool:
        return await self._store.remove(conversation_id)

    async def list_all(
        self,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {}
        if user_id is not None:
            filters["user_id"] = user_id
        if project_id is not None:
            filters["project_id"] = project_id
        return await self._store.list_all(**filters)

    async def update_fields(
        self,
        conversation_id: str,
        **fields: object,
    ) -> None:
        """Update arbitrary fields on a conversation and persist."""
        conv = await self.get(conversation_id)
        if conv is not None:
            conv.update(fields)
            await self._store.put(conversation_id, conv)

    async def add_message(
        self,
        conversation_id: str,
        *,
        user_id: str,
        display_name: str | None,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        from lintel.contracts.data_models import ChatMessage

        conv = await self.get(conversation_id)
        if conv is None:
            msg = f"Conversation {conversation_id} not found"
            raise KeyError(msg)
        message = ChatMessage(
            message_id=uuid4().hex,
            user_id=user_id,
            display_name=display_name,
            role=role,
            content=content,
            timestamp=datetime.now(UTC).isoformat(),
        )
        data = message.model_dump()
        conv["messages"].append(data)
        await self._store.put(conversation_id, conv)
        return data


class PostgresSandboxStore:
    """Postgres-backed sandbox metadata store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "sandbox")

    async def add(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        await self._store.put(sandbox_id, metadata)

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return await self._store.get(sandbox_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._store.list_all()

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        await self._store.put(sandbox_id, metadata)

    async def remove(self, sandbox_id: str) -> None:
        await self._store.remove(sandbox_id)


class PostgresAgentDefinitionStore:
    """Postgres-backed agent definition store (async methods)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._store = PostgresDictStore(pool, "agent_definition")

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._store.list_all()

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        return await self._store.get(agent_id)

    async def create(self, definition: dict[str, Any]) -> dict[str, Any]:
        agent_id = definition["agent_id"]
        existing = await self.get(agent_id)
        if existing is not None:
            msg = f"Agent definition '{agent_id}' already exists"
            raise ValueError(msg)
        await self._store.put(agent_id, definition)
        return definition

    async def update(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get(agent_id)
        if existing is None:
            raise KeyError(agent_id)
        existing.update(updates)
        await self._store.put(agent_id, existing)
        return existing

    async def delete(self, agent_id: str) -> None:
        existing = await self.get(agent_id)
        if existing is None:
            raise KeyError(agent_id)
        await self._store.remove(agent_id)


class PostgresModelStore(PostgresCrudStore):
    """Postgres-backed model store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import Model

        super().__init__(pool, "model", "model_id", Model)

    async def list_by_provider(self, provider_id: str) -> list[Any]:
        return await self.list_all(provider_id=provider_id)


class PostgresModelAssignmentStore(PostgresCrudStore):
    """Postgres-backed model assignment store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import ModelAssignment

        super().__init__(pool, "model_assignment", "assignment_id", ModelAssignment)

    async def list_by_model(self, model_id: str) -> list[Any]:
        return await self.list_all(model_id=model_id)

    async def list_by_context(
        self,
        context: Any,  # noqa: ANN401
        context_id: str | None = None,
    ) -> list[Any]:
        filters: dict[str, Any] = {"context": str(context)}
        if context_id is not None:
            filters["context_id"] = context_id
        return await self.list_all(**filters)

    async def remove_by_model(self, model_id: str) -> None:
        """Remove all assignments for a given model."""
        assignments = await self.list_by_model(model_id)
        for a in assignments:
            await self.remove(a.assignment_id)


class PostgresSkillStore(PostgresCrudStore):
    """Postgres-backed skill store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import SkillDescriptor

        super().__init__(pool, "skill", "name", SkillDescriptor)
        self._skill_ids: dict[str, str] = {}  # skill_id -> name mapping

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
    ) -> SkillDescriptor:
        from lintel.contracts.types import SkillDescriptor, SkillExecutionMode

        descriptor = SkillDescriptor(
            name=name,
            version=version,
            input_schema=input_schema,
            output_schema=output_schema,
            execution_mode=SkillExecutionMode(execution_mode),
        )
        # Store with skill_id as entity_id
        from lintel.infrastructure.persistence.crud_store import _serialize

        data = _serialize(descriptor)
        data["_skill_id"] = skill_id
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                self._kind,
                skill_id,
                json.dumps(data, default=str),
            )
        return descriptor

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        from lintel.contracts.types import SkillResult

        raw = await self.get(skill_id, raw=True)
        if raw is None:
            msg = f"Skill {skill_id} not found"
            raise KeyError(msg)
        return SkillResult(success=True, output={"echo": input_data})

    async def delete(self, skill_id: str) -> None:
        await self.remove(skill_id)

    async def list_skills(self) -> dict[str, Any]:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(
                "SELECT entity_id, data FROM entities WHERE kind = $1 ORDER BY created_at",
                self._kind,
            )
            result: dict[str, Any] = {}
            for row in rows:
                data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                skill_id = row["entity_id"]
                data.pop("_skill_id", None)
                result[skill_id] = self._to_instance(data)
            return result
