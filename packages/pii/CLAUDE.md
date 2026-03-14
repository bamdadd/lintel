# lintel-pii

PII detection and anonymization using Microsoft Presidio — fail-closed, per-thread stable placeholders.

## Key exports

- `PresidioFirewall` — implements `Deidentifier` protocol; detects and anonymizes PII using `AnalyzerEngine`; returns `DeidentifyResultImpl` with `sanitized_text`, `risk_score`, and `is_blocked`
- `PlaceholderManager` — generates stable, per-thread placeholders like `<PERSON_1>`, `<EMAIL_2>`; stores mappings for reversible anonymization
- `custom_recognizers` — additional Presidio recognizers for domain-specific entity types

## Dependencies

- `lintel-contracts` — `PIIVault` protocol, `ThreadRef`
- `presidio-analyzer>=2.2`, `presidio-anonymizer>=2.2`, `structlog>=24.4`

## Tests

```bash
make test-pii
# or: uv run pytest packages/pii/tests/ -v
```

## Usage

```python
from lintel.pii.presidio_firewall import PresidioFirewall
from lintel.pii.placeholder_manager import PlaceholderManager

firewall = PresidioFirewall(vault=vault, risk_threshold=0.6)
result = await firewall.deidentify("Call John at john@example.com", thread_ref)
# result.sanitized_text == "Call <PERSON_1> at <EMAIL_1>"
```
