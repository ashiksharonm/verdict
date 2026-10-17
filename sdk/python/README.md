# verdict-sdk

Python client for the [Verdict API](../../docs/API.md): `pii`, `toxicity`, `prompt_injection` and `grounded` checks
with calibrated scores. Not published to PyPI yet; install from the repo: `pip install ./sdk/python`.

```python
from verdict import Client, assert_checks

client = Client(api_key="vk_...")            # or set VERDICT_API_KEY
r = client.check("Call me on 415-555-0132", checks=["pii", "toxicity"])
r["pii"].flagged, r["pii"].score             # True, 0.97

client.check("Paris is in Italy.", checks=["grounded"], context="Paris is the capital of France.")
```

Async: `async with AsyncClient(api_key=...) as c: await c.check(...)`. Batches: `check_batch([...])` (up to 32)
or `check_many(texts)`.

Retries (3 by default) cover 429, 502, 503, 504 and network errors; a `Retry-After` header is honoured, otherwise
backoff is exponential with jitter. 401 raises `AuthError`, other 4xx `InvalidRequest`, exhausted 429s `RateLimitError`.

CI gate: fail a pipeline when a prompt change makes outputs leak PII or hallucinate.

```python
results = client.check_many(model_outputs, checks=["pii", "toxicity"])
assert_checks(results, max_rate={"pii": 0.0, "toxicity": 0.02})   # raises AssertionError listing violations
```
