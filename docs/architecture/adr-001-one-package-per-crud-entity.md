# ADR-001: One Package Per CRUD Entity with Isolated Tests

**Status:** Accepted
**Date:** 2026-03-15
**Deciders:** Bamdad

## Context

`packages/app/` grew into a monolith with 40 route modules and 400+ tests. Any change to one CRUD entity triggered all tests. Developer feedback loops were slow and test failures were noisy.

## Decision

Every CRUD entity gets its own uv workspace package under `packages/` with:

1. Its own `store.py` and `routes.py`
2. Its own `tests/` directory with a lightweight FastAPI test harness that boots only that router
3. A `StoreProvider` from `lintel-api-support` instead of the app-level DI container

The `app` package becomes a thin composition root that imports routers and wires stores at startup.

**New features MUST follow this pattern** — never add new CRUD routes directly to `packages/app/`.

### Package template

```
packages/<entity>/
├── pyproject.toml
├── src/lintel/<entity>/
│   ├── __init__.py
│   ├── py.typed
│   ├── store.py      # InMemory store class
│   └── routes.py     # FastAPI router + request/response models + StoreProvider
└── tests/
    ├── conftest.py    # Lightweight fixture: builds minimal FastAPI app with just this router
    └── test_routes.py # HTTP tests via TestClient
```

### Test isolation pattern

```python
# tests/conftest.py — each package builds its OWN minimal app
@pytest.fixture()
def client():
    store = InMemoryFooStore()
    foo_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    foo_store_provider.override(None)
```

## Alternatives Considered

**Option B: Group related entities into ~8 domain packages** (e.g., `lintel-iam` for users+teams+policies). Rejected because it still couples unrelated entities and doesn't give full test isolation per entity.

## Consequences

- ~30 small packages instead of 1 large one
- Each package runs only its own tests (5-15 tests, sub-second)
- `Makefile` has `test-<name>` targets per package
- Trade-off: more `pyproject.toml` files to maintain, but the boilerplate is mechanical and templated
- `make test-affected` automatically detects which packages changed and runs only those tests
