# lintel-improvement-api

Auto-improvement loop API — failure classification, improvement ledger, and anti-overfitting guard.

## Key modules

- `src/lintel/improvement_api/types.py` — Domain types: `ImprovementEntry`, `FailureDistribution`, `OverfitCheck`
- `src/lintel/improvement_api/store.py` — `InMemoryImprovementStore` for ledger entries
- `src/lintel/improvement_api/routes.py` — API endpoints for classify, ledger CRUD, distribution, overfit-check
- `src/lintel/improvement_api/overfit_guard.py` — Anti-overfitting validation logic

## Related

- `packages/workflows/src/lintel/workflows/failure_classifier.py` — `FailureClassifier` that categorises stage failures into root cause classes

## Testing

```bash
uv run pytest packages/improvement-api/tests/ packages/workflows/tests/test_failure_classifier.py -v
```
