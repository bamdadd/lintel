# Codebase Survey: Python Backend

## Contracts Layer

### `src/lintel/contracts/protocols.py`
- **SandboxManager Protocol** (lines 137-164): Uses primitive parameters (`job_id: UUID, repo_url: str, base_sha: str, branch_name: str`). Methods: `create_sandbox`, `execute_command`, `collect_artifacts`, `destroy_sandbox`.
- **CommandResult Protocol** (lines 131-134): Defines `exit_code: int`, `stdout: str`, `stderr: str`. Redundant with `SandboxResult` dataclass.
- All other Protocols (`EventStore`, `Deidentifier`, `ChannelAdapter`, `ModelRouter`, `CredentialStore`, `RepositoryStore`, `RepoProvider`, `SkillRegistry`) use typed value objects from `contracts/types.py`.

### `src/lintel/contracts/types.py`
- **SandboxConfig** (lines 160-165): Minimal — `image: str`, `memory_limit: str`, `cpu_quota: int`. Missing: `network_enabled`, `timeout_seconds`, `environment`, `repo_url`, `credential_id`.
- **SandboxJob** (lines 168-173): `command: str`, `workdir: str | None`. Missing: `timeout_seconds`.
- **SandboxResult** (lines 177-183): `exit_code: int`, `stdout: str`, `stderr: str`. Well-designed.
- **SandboxStatus** (lines 111-118): Complete lifecycle enum (`PENDING`, `CREATING`, `RUNNING`, `COLLECTING`, `COMPLETED`, `FAILED`, `DESTROYED`).
- All types use `@dataclass(frozen=True)` — immutable value objects per codebase convention.

### `src/lintel/contracts/events.py`
- Sandbox events already defined: `SandboxJobScheduled`, `SandboxCreated`, `SandboxArtifactsCollected`, `SandboxDestroyed`.
- Wrapped in `EventEnvelope` with `correlation_id`, `causation_id`, `timestamp`.

### `src/lintel/contracts/commands.py`
- `ScheduleSandboxJob` command defined with `thread_ref`, `job_id`, `repo_url`, `base_sha`, `branch_name`.

## Infrastructure Layer

### `src/lintel/infrastructure/sandbox/docker_backend.py`
- **DockerSandboxManager** class — single sandbox implementation.
- Method names: `create`, `execute`, `collect_artifacts`, `destroy` — **differ from contracts Protocol**.
- Signature: `create(config: SandboxConfig, thread_ref: ThreadRef)` — uses typed value objects.
- Security hardening: `cap_drop=["ALL"]`, `read_only=True`, `network_mode="none"`, `user="1000:1000"`, `no-new-privileges`, `tmpfs` with `noexec`.
- Missing: `demux=True` on `exec_run` (stderr lost), no execution timeout, no error handling, in-memory `_containers` dict.
- Uses `asyncio.to_thread` for sync Docker SDK — correct pattern.

### `src/lintel/infrastructure/sandbox/__init__.py`
- Empty file.

## Domain Layer

### `src/lintel/domain/sandbox/protocols.py`
- **Duplicate SandboxManager Protocol** — defines `create(config, thread_ref)`, `execute(sandbox_id, job)`, `collect_artifacts(sandbox_id)`, `destroy(sandbox_id)`.
- Uses typed value objects (`SandboxConfig`, `SandboxJob`, `SandboxResult`, `ThreadRef`).
- This is what `DockerSandboxManager` actually satisfies (structurally).
- **Should not exist** — Protocols belong in `contracts/protocols.py` per architecture.

## API Layer

### `src/lintel/api/routes/sandboxes.py`
- REST routes: `POST /sandboxes`, `GET /sandboxes/{id}`, `POST /sandboxes/{id}/execute`, `DELETE /sandboxes/{id}`.
- Uses **in-memory dict** (`_sandboxes = {}`) — not wired to `DockerSandboxManager`.
- Should use `request.app.state.sandbox_manager` via FastAPI DI.

### `src/lintel/api/app.py`
- Lifespan function instantiates services into `app.state`.
- `SandboxManager` is **not instantiated** in lifespan — not wired.

## Test Layer

### `tests/unit/contracts/test_protocols.py`
- Conformance test for `SandboxManager` exists but uses **wrong method signatures** (matches neither Protocol).
- Will fail at runtime.

## Established Conventions
- `typing.Protocol` for all service boundaries (no ABC)
- `@dataclass(frozen=True)` for value objects
- `TYPE_CHECKING` guards for import-time performance
- `asyncio.to_thread` for sync SDK wrapping
- Constructor injection via FastAPI `app.state`
- `PresidioFirewall` is the gold-standard Protocol implementation reference
