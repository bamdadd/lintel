# lintel-persistence

Generic Postgres-backed CRUD and dict stores for frozen dataclasses, plus an encrypted vault.

## Key exports

- `PostgresCrudStore` — generic Postgres store for frozen dataclasses; handles nested dataclass reconstruction via `_reconstruct_nested`
- `PostgresDictStore` — JSONB-backed dict store for schema-less entities (chat, work items)
- `PostgresEntityStore` — base class with common upsert/get/list/delete helpers
- `PostgresRepositoryStore`, `PostgresCredentialStore`, `PostgresAIProviderStore`, `PostgresSkillStore` — typed stores with custom query methods (in `stores.py`)
- `PostgresVault` — encrypted secret store using `cryptography` (in `vault/postgres_vault.py`)
- `InMemoryProjectionStore` — dict-backed projection state store for tests

## Dependencies

- `lintel-contracts` — domain types (`Repository`, `Credential`, etc.)
- `asyncpg>=0.30`, `sqlalchemy[asyncio]>=2.0`, `pydantic>=2.10`, `cryptography>=44.0`

## Tests

```bash
make test-persistence
# or: uv run pytest packages/persistence/tests/ -v
```

## Usage

```python
from lintel.persistence.crud_store import PostgresCrudStore
from lintel.persistence.stores import PostgresRepositoryStore
from lintel.persistence.vault.postgres_vault import PostgresVault

repo_store = PostgresRepositoryStore(pool)
repo = await repo_store.get_by_url("https://github.com/org/repo")
```
