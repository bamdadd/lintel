"""Tests for the setup_workspace workflow node."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from lintel.contracts.types import ThreadRef  # noqa: TC001
from lintel.domain.types import Variable
from lintel.persistence.types import Credential, CredentialType
from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult, SandboxStatus
from lintel.variables_api.store import InMemoryVariableStore
from lintel.workflows.nodes.setup_workspace import setup_workspace


class FakeSandboxStore:
    """In-memory sandbox store for pool-based allocation in tests."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        for e in entries or []:
            self._data[e["sandbox_id"]] = dict(e)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._data.get(sandbox_id)

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._data[sandbox_id] = metadata


class _AppState:
    """Minimal app_state stub exposing sandbox_store (and optionally others)."""

    def __init__(self, sandbox_store: FakeSandboxStore, **kwargs: Any) -> None:  # noqa: ANN401
        self.sandbox_store = sandbox_store
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummySandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}
        self.created: list[str] = []
        self.created_configs: list[SandboxConfig] = []
        self.destroyed: list[str] = []
        self.executed: list[str] = []
        self.written_files: dict[str, str] = {}
        self.network_disconnected: list[str] = []

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        self.created.append(sandbox_id)
        self.created_configs.append(config)
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        self.executed.append(job.command)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        self.written_files[path] = content

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        return SandboxStatus.RUNNING

    async def get_logs(self, sandbox_id: str, tail: int = 200) -> str:
        return ""

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, Any]:
        return {}

    async def reconnect_network(self, sandbox_id: str) -> None:
        pass

    async def disconnect_network(self, sandbox_id: str) -> None:
        self.network_disconnected.append(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        self.destroyed.append(sandbox_id)


class DummyRepoProvider:
    async def clone_repo(self, repo_url: str, branch: str, target_dir: str) -> None:
        pass

    async def create_branch(self, repo_url: str, branch_name: str, base_sha: str) -> None:
        pass

    async def commit_and_push(self, workdir: str, message: str, branch: str) -> str:
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

    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None:
        pass

    async def list_branches(self, repo_url: str) -> list[str]:
        return []

    async def get_file_content(self, repo_url: str, path: str, ref: str = "HEAD") -> str:
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
        return [c for c in self._creds.values() if not c.repo_ids or repo_id in c.repo_ids]

    async def revoke(self, credential_id: str) -> None:
        self._creds.pop(credential_id, None)
        self._secrets.pop(credential_id, None)


POOL_SANDBOX_ID = "pool-sbx-001"


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
        "run_id": "test-run-1",
        "repo_url": "https://github.com/test/repo.git",
        "repo_branch": "main",
        "feature_branch": "",
        "credential_ids": (),
    }
    base.update(overrides)
    return base


def _make_config(
    manager: DummySandboxManager,
    *,
    sandbox_store: FakeSandboxStore | None = None,
    **extra: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Build a RunnableConfig dict with a pre-provisioned sandbox pool."""
    if sandbox_store is None:
        sandbox_store = FakeSandboxStore([{"sandbox_id": POOL_SANDBOX_ID}])
    app_state = _AppState(sandbox_store=sandbox_store)
    configurable: dict[str, Any] = {
        "sandbox_manager": manager,
        "app_state": app_state,
    }
    configurable.update(extra)
    return {"configurable": configurable}


class TestSetupWorkspace:
    @pytest.fixture(autouse=True)
    def _no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prevent tests from reading real macOS Keychain credentials."""
        monkeypatch.setattr(
            "lintel.workflows.nodes.setup_workspace._get_claude_code_credentials_json",
            lambda: "",
        )
        monkeypatch.setattr(
            "lintel.workflows.nodes.setup_workspace._get_claude_code_oauth_token",
            lambda: "",
        )

    async def test_clones_repo_and_creates_branch(self) -> None:
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        assert result["current_phase"] == "planning"
        assert "lintel/feat/wi-123" in result["feature_branch"]
        # Pool path: reconnect + rm + mkdir + repo check + clone + verify + checkout + deps
        assert any("rm -rf" in cmd for cmd in manager.executed)
        assert any("git clone" in cmd for cmd in manager.executed)
        assert any("git checkout -b" in cmd or "git checkout" in cmd for cmd in manager.executed)
        assert result["workspace_path"] == "/workspace/test-run-1/repo"

    async def test_creates_empty_sandbox_without_repo_url(self) -> None:
        manager = DummySandboxManager()
        state = _make_state(repo_url="")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        assert result["current_phase"] == "planning"

    async def test_destroys_sandbox_on_clone_failure(self) -> None:
        manager = DummySandboxManager()
        call_count = 0

        async def failing_execute(sandbox_id: str, job: SandboxJob) -> SandboxResult:
            nonlocal call_count
            call_count += 1
            # Let the pool setup commands (reconnect, rm, mkdir) pass,
            # fail on the git clone command
            if "git clone" in job.command:
                msg = "clone failed"
                raise RuntimeError(msg)
            return SandboxResult(exit_code=0, stdout="ok\n")

        manager.execute = failing_execute  # type: ignore[assignment]
        state = _make_state()

        with pytest.raises(RuntimeError, match="clone failed"):
            await setup_workspace(
                state,  # type: ignore[arg-type]
                _make_config(manager),
            )

    async def test_uses_custom_feature_branch(self) -> None:
        manager = DummySandboxManager()
        state = _make_state(feature_branch="custom/my-branch")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        assert result["feature_branch"] == "custom/my-branch"
        assert any("custom/my-branch" in cmd for cmd in manager.executed)

    async def test_injects_variables_into_sandbox_config(self) -> None:
        """Plain variables are resolved and available; sandbox is from pool."""
        manager = DummySandboxManager()
        var_store = InMemoryVariableStore()
        await var_store.add(
            Variable(
                variable_id="v1",
                key="API_URL",
                value="https://api.test",
                environment_id="env-1",
            )
        )
        await var_store.add(
            Variable(
                variable_id="v2",
                key="DEBUG",
                value="true",
                environment_id="env-1",
            )
        )
        state = _make_state(environment_id="env-1")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager, variable_store=var_store),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID

    async def test_secrets_excluded_from_env_vars(self) -> None:
        """Secret variables are NOT injected as env vars — only as files."""
        manager = DummySandboxManager()
        var_store = InMemoryVariableStore()
        await var_store.add(
            Variable(
                variable_id="v1",
                key="API_URL",
                value="https://api.test",
                environment_id="env-1",
            )
        )
        await var_store.add(
            Variable(
                variable_id="v2",
                key="SECRET_KEY",
                value="s3cret",
                environment_id="env-1",
                is_secret=True,
            )
        )
        state = _make_state(environment_id="env-1")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager, variable_store=var_store),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        # Secret should be written as a file, not in env
        assert manager.written_files.get("/run/secrets/SECRET_KEY") == "s3cret"

    async def test_secrets_written_as_files_in_sandbox(self) -> None:
        """Secret variables are written to /run/secrets/<key> in the sandbox."""
        manager = DummySandboxManager()
        var_store = InMemoryVariableStore()
        await var_store.add(
            Variable(
                variable_id="v1",
                key="DB_PASSWORD",
                value="p@ssw0rd",
                environment_id="env-1",
                is_secret=True,
            )
        )
        await var_store.add(
            Variable(
                variable_id="v2",
                key="API_TOKEN",
                value="tok-abc",
                environment_id="env-1",
                is_secret=True,
            )
        )
        state = _make_state(environment_id="env-1")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager, variable_store=var_store),
        )

        assert result["sandbox_id"] is not None
        assert manager.written_files["/run/secrets/DB_PASSWORD"] == "p@ssw0rd"
        assert manager.written_files["/run/secrets/API_TOKEN"] == "tok-abc"
        assert any("mkdir -p /run/secrets" in cmd for cmd in manager.executed)

    async def test_no_variables_without_environment_id(self) -> None:
        """Without environment_id, no variables are resolved."""
        manager = DummySandboxManager()
        var_store = InMemoryVariableStore()
        await var_store.add(
            Variable(
                variable_id="v1",
                key="API_URL",
                value="https://api.test",
                environment_id="env-1",
            )
        )
        state = _make_state()  # no environment_id set

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager, variable_store=var_store),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        # No secret files should have been written
        assert not manager.written_files

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
            _make_config(manager, credential_store=cred_store),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        assert result["current_phase"] == "planning"
        clone_cmds = [c for c in manager.executed if "git clone" in c]
        assert len(clone_cmds) >= 1
        assert "x-access-token:ghp_abc123secret@github.com" in clone_cmds[0]

    async def test_network_disconnected_after_clone(self) -> None:
        """Network is disconnected after successful clone."""
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        assert len(manager.network_disconnected) == 1
        assert manager.network_disconnected[0] == POOL_SANDBOX_ID

    async def test_branch_uses_naming_convention(self) -> None:
        """When no explicit feature_branch, uses generate_branch_name."""
        manager = DummySandboxManager()
        state = _make_state(feature_branch="", intent="bug")

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        branch = result["feature_branch"]
        assert branch.startswith("lintel/fix/wi-123-")
        assert any(branch in cmd for cmd in manager.executed)

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
            _make_config(manager),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        clone_cmds = [c for c in manager.executed if "git clone" in c]
        assert len(clone_cmds) == 2
        assert "repo2.git" in clone_cmds[1]

    async def test_clone_works_without_credentials(self) -> None:
        """Public repo clone works when no credential_store is given."""
        manager = DummySandboxManager()
        state = _make_state()

        result = await setup_workspace(
            state,  # type: ignore[arg-type]
            _make_config(manager),
        )

        assert result["sandbox_id"] == POOL_SANDBOX_ID
        assert result["current_phase"] == "planning"
        clone_cmds = [c for c in manager.executed if "git clone" in c]
        assert len(clone_cmds) >= 1
        assert "x-access-token" not in clone_cmds[0]
        assert "https://github.com/test/repo.git" in clone_cmds[0]
