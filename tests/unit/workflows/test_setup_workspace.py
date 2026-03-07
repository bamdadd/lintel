"""Tests for the setup_workspace workflow node."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from lintel.api.routes.variables import InMemoryVariableStore
from lintel.contracts.types import (
    Credential,
    CredentialType,
    SandboxConfig,
    SandboxJob,
    SandboxResult,
    SandboxStatus,
    ThreadRef,
    Variable,
)
from lintel.workflows.nodes.setup_workspace import setup_workspace


class DummySandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}
        self.created: list[str] = []
        self.created_configs: list[SandboxConfig] = []
        self.destroyed: list[str] = []
        self.executed: list[str] = []
        self.written_files: dict[str, str] = {}
        self.network_disconnected: list[str] = []

    async def create(
        self, config: SandboxConfig, thread_ref: ThreadRef
    ) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        self.created.append(sandbox_id)
        self.created_configs.append(config)
        return sandbox_id

    async def execute(
        self, sandbox_id: str, job: SandboxJob
    ) -> SandboxResult:
        self.executed.append(job.command)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(
        self, sandbox_id: str, path: str, content: str
    ) -> None:
        self.written_files[path] = content

    async def list_files(
        self, sandbox_id: str, path: str = "/workspace"
    ) -> list[str]:
        return []

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        return SandboxStatus.RUNNING

    async def collect_artifacts(
        self, sandbox_id: str
    ) -> dict[str, Any]:
        return {}

    async def disconnect_network(self, sandbox_id: str) -> None:
        self.network_disconnected.append(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        self.destroyed.append(sandbox_id)


class DummyRepoProvider:
    async def clone_repo(
        self, repo_url: str, branch: str, target_dir: str
    ) -> None:
        pass

    async def create_branch(
        self, repo_url: str, branch_name: str, base_sha: str
    ) -> None:
        pass

    async def commit_and_push(
        self, workdir: str, message: str, branch: str
    ) -> str:
        return "abc123"

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        return "https://github.com/test/repo/pull/1"

    async def add_comment(
        self, repo_url: str, pr_number: int, body: str
    ) -> None:
        pass

    async def list_branches(self, repo_url: str) -> list[str]:
        return []

    async def get_file_content(
        self, repo_url: str, path: str, ref: str = "HEAD"
    ) -> str:
        return ""

    async def list_commits(
        self, repo_url: str, branch: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        return []


class DummyCredentialStore:
    def __init__(self) -> None:
        self._creds: dict[str, Credential] = {}
        self._secrets: dict[str, str] = {}

    async def store(
        self,
        credential_id: str,
        credential_type: str,
        name: str,
        secret: str,
        repo_ids: list[str] | None = None,
    ) -> Credential:
        cred = Credential(
            credential_id=credential_id,
            credential_type=CredentialType(credential_type),
            name=name,
            repo_ids=frozenset(repo_ids or []),
        )
        self._creds[credential_id] = cred
        self._secrets[credential_id] = secret
        return cred

    async def get(self, credential_id: str) -> Credential | None:
        return self._creds.get(credential_id)

    async def get_secret(self, credential_id: str) -> str | None:
        return self._secrets.get(credential_id)

    async def list_all(self) -> list[Credential]:
        return list(self._creds.values())

    async def list_by_repo(self, repo_id: str) -> list[Credential]:
        return [
            c
            for c in self._creds.values()
            if not c.repo_ids or repo_id in c.repo_ids
        ]

    async def revoke(self, credential_id: str) -> None:
        self._creds.pop(credential_id, None)
        self._secrets.pop(credential_id, None)


def _make_state(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    base: dict[str, Any] = {
        "thread_ref": "thread:W1:C1:1.0",
        "correlation_id": str(uuid4()),
        "current_phase": "routing",
        "sanitized_messages": ["add a button"],
        "intent": "feature",
        "plan": {},
        "agent_outputs": [],
        "pending_approvals": [],
        "sandbox_id": None,
        "sandbox_results": [],
        "pr_url": "",
        "error": None,
        "project_id": "proj-1",
        "work_item_id": "wi-123",
        "repo_url": "https://github.com/test/repo.git",
        "repo_branch": "main",
        "feature_branch": "",
        "credential_ids": (),
    }
    base.update(overrides)
    return base


class TestSetupWorkspace:
    async def test_clones_repo_and_creates_branch(self) -> None:
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["sandbox_id"] is not None
        assert result["current_phase"] == "planning"
        assert "lintel/feat/wi-123" in result["feature_branch"]
        assert len(manager.created) == 1
        assert len(manager.executed) == 2  # clone + checkout
        assert "git clone" in manager.executed[0]
        assert "git checkout -b" in manager.executed[1]

    async def test_returns_error_without_repo_url(self) -> None:
        manager = DummySandboxManager()
        state = _make_state(repo_url="")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["error"] is not None
        assert result["current_phase"] == "closed"
        assert len(manager.created) == 0

    async def test_destroys_sandbox_on_clone_failure(self) -> None:
        manager = DummySandboxManager()

        async def failing_execute(
            sandbox_id: str, job: SandboxJob
        ) -> SandboxResult:
            msg = "clone failed"
            raise RuntimeError(msg)

        manager.execute = failing_execute  # type: ignore[assignment]
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["error"] is not None
        assert result["sandbox_id"] is None
        assert len(manager.destroyed) == 1

    async def test_uses_custom_feature_branch(self) -> None:
        manager = DummySandboxManager()
        state = _make_state(feature_branch="custom/my-branch")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["feature_branch"] == "custom/my-branch"
        assert "custom/my-branch" in manager.executed[1]

    async def test_injects_variables_into_sandbox_config(self) -> None:
        manager = DummySandboxManager()
        store = InMemoryVariableStore()
        await store.add(Variable(
            variable_id="v1", key="API_URL", value="https://api.test",
            environment_id="env-1",
        ))
        await store.add(Variable(
            variable_id="v2", key="SECRET_KEY", value="s3cret",
            environment_id="env-1", is_secret=True,
        ))
        state = _make_state(environment_id="env-1")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider(), "variable_store": store}},
        )

        assert result["sandbox_id"] is not None
        config = manager.created_configs[0]
        env_dict = dict(config.environment)
        assert env_dict["API_URL"] == "https://api.test"
        assert env_dict["SECRET_KEY"] == "s3cret"

    async def test_no_variables_without_environment_id(self) -> None:
        manager = DummySandboxManager()
        store = InMemoryVariableStore()
        await store.add(Variable(
            variable_id="v1", key="API_URL", value="https://api.test",
            environment_id="env-1",
        ))
        state = _make_state()  # no environment_id set

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider(), "variable_store": store}},
        )

        assert result["sandbox_id"] is not None
        config = manager.created_configs[0]
        assert config.environment == frozenset()

    async def test_injects_github_token_into_clone_url(self) -> None:
        """Credentials with github_token type inject token into URL."""
        manager = DummySandboxManager()
        cred_store = DummyCredentialStore()
        await cred_store.store(
            credential_id="cred-1",
            credential_type="github_token",
            name="My Token",
            secret="ghp_abc123secret",
        )
        state = _make_state(credential_ids=("cred-1",))

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider(), "credential_store": cred_store}},
        )

        assert result["sandbox_id"] is not None
        assert result["current_phase"] == "planning"
        clone_cmd = manager.executed[0]
        assert "x-access-token:ghp_abc123secret@github.com" in clone_cmd

    async def test_network_disconnected_after_clone(self) -> None:
        """Network is disconnected after successful clone."""
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["sandbox_id"] is not None
        assert len(manager.network_disconnected) == 1
        assert manager.network_disconnected[0] == result["sandbox_id"]

    async def test_branch_uses_naming_convention(self) -> None:
        """When no explicit feature_branch, uses generate_branch_name."""
        manager = DummySandboxManager()
        state = _make_state(feature_branch="", intent="bug")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        branch = result["feature_branch"]
        # Should follow lintel/fix/<id[:8]>-<slug> pattern for bug intent
        assert branch.startswith("lintel/fix/wi-123-")
        assert "git checkout -b" in manager.executed[1]
        assert branch in manager.executed[1]

    async def test_multi_repo_clones_additional_repos(self) -> None:
        """When repo_urls has multiple entries, additional repos are cloned."""
        manager = DummySandboxManager()
        state = _make_state(
            repo_urls=(
                "https://github.com/test/repo.git",
                "https://github.com/test/repo2.git",
            ),
        )

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["sandbox_id"] is not None
        # Primary clone + checkout + secondary clone = 3 commands
        assert len(manager.executed) == 3
        assert "/workspace/repo-1" in manager.executed[2]
        assert "repo2.git" in manager.executed[2]

    async def test_clone_works_without_credentials(self) -> None:
        """Public repo clone works when no credential_store is given."""
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            {"configurable": {"sandbox_manager": manager, "repo_provider": DummyRepoProvider()}},
        )

        assert result["sandbox_id"] is not None
        assert result["current_phase"] == "planning"
        clone_cmd = manager.executed[0]
        # URL should be unchanged — no token injection
        assert "x-access-token" not in clone_cmd
        assert "https://github.com/test/repo.git" in clone_cmd
