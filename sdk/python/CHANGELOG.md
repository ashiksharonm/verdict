# Changelog

## 0.1.0

First release of `verdict-guardrails`.

- `Client` and `AsyncClient` for `/v1/check` and `/v1/check/batch`, with `check_many` chunking into batches of 32.
- Retries with jittered backoff for 429/502/503/504 and connection failures; honours `Retry-After`.
- Typed errors: `AuthError`, `RateLimitError`, `InvalidRequest`, `VerdictError`.
- `assert_checks` / `flag_rates` for gating CI on flagged rates.
