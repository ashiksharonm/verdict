# Verdict API

Base URL: `https://ashiksharon005-verdict-api.hf.space` (free Hugging Face Space; it sleeps when idle, so the first
call after a long pause can take a minute). OpenAPI: `GET /openapi.json`, Swagger UI at `/docs`.

All errors are JSON: `{"error": {"code": "<machine_code>", "message": "<text>"}}`. Every response carries
`X-Request-ID` (your own value is echoed if it matches `[A-Za-z0-9._-]{1,64}`, otherwise one is generated).

## Checks

| name | fires when | needs |
|---|---|---|
| `pii` | text contains personal data | `text` |
| `toxicity` | text is toxic, insulting, obscene, hateful or threatening | `text` |
| `prompt_injection` | text tries to override an assistant's instructions or jailbreak it | `text` |
| `grounded` | the response (`text`) is **not** supported by `context` | `text` and `context` |

`score` is the calibrated probability that the check fires (for `grounded`: that the response is unsupported).
`flagged = score >= threshold`; thresholds are per check, chosen on validation data (`GET` them from any response).
The model reads at most 512 tokens per input; longer text or context is truncated. Default checks are all except
`grounded`.

## POST /v1/check

Auth: `Authorization: Bearer vk_...`

```json
{"text": "Call me on 415-555-0132", "checks": ["pii", "toxicity"], "context": null}
```

`text` 1-20,000 chars; `checks` 1-4 unique names (default `["pii","toxicity","prompt_injection"]`); `context` up to
50,000 chars, required when `grounded` is requested. Unknown fields are rejected (422).

```json
{"id": "chk_9f2c...", "model_version": "verdict-laya@<rev>-int8",
 "results": {"pii": {"flagged": true, "score": 0.97, "threshold": 0.63},
             "toxicity": {"flagged": false, "score": 0.02, "threshold": 0.53}},
 "latency_ms": 41.2}
```

## POST /v1/check/batch

`{"items": [<check body>, ...]}` with 1-32 items. Response `{"results": [<check response>, ...]}` in input order.
A batch of N items counts as N requests against rate limit and quota.

## POST /v1/playground/check

Anonymous. Same body and response as `/v1/check`. Requires header `X-Turnstile-Token` (Cloudflare Turnstile widget
token; verified server-side). 400 `missing_turnstile_token` if absent, 403 `turnstile_failed` if rejected.
Limit 10 requests/min per IP; if the limiter backend is down the endpoint answers 503 (fails closed).

## Keys and usage (dashboard)

Auth: `Authorization: Bearer <Supabase access token>` (the signed-in user's session token).

| method | path | body / result |
|---|---|---|
| `POST` | `/v1/keys` | `{"name": "ci"}` -> 201 `{"id","key","prefix","name","created_at"}`. `key` is shown once; only its sha256 is stored. Max 5 active keys (409 `key_limit`). |
| `GET` | `/v1/keys` | `{"keys": [{"id","name","prefix","created_at","revoked_at","monthly_quota"}]}` (newest first, includes revoked) |
| `DELETE` | `/v1/keys/{id}` | 204; 404 if not yours or already revoked. A revoked key stops working within 60 s. |
| `GET` | `/v1/usage` | `{"month":"2026-10","days":[{"day","count"}],"month_total":n,"quota":10000,"keys":[{"id","name","prefix","month_count","quota"}]}` |

`days` covers the last 31 days summed over the user's keys. `quota` is the monthly quota of each active key.
If the database tables are not created yet these endpoints answer 503 `database_unavailable`.

## Meta

`GET /v1/checks` (names, descriptions, `default`, `requires_context`), `GET /healthz` (process up),
`GET /readyz` (200 once the model is loaded, else 503 with `error` if loading failed), `GET /metrics` (Prometheus).

## Limits and headers

Per API key: 60 requests/min and 10,000/month (server-configurable). Authenticated responses carry
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (unix seconds). A limited request gets
`429` with `Retry-After` (seconds) and the same headers; code `rate_limited` or `quota_exceeded`. If Redis is
unreachable, authenticated requests are served without limiting (a warning is logged).

## Status codes

| status | codes |
|---|---|
| 400 | `missing_turnstile_token` |
| 401 | `missing_api_key`, `invalid_api_key`, `missing_token`, `invalid_token` |
| 403 | `turnstile_failed` |
| 404 | `not_found` |
| 409 | `key_limit` |
| 413 | `payload_too_large` (body over 2.5 MB) |
| 422 | `invalid_request` (message names the field) |
| 429 | `rate_limited`, `quota_exceeded` |
| 503 | `model_loading`, `busy` (retry after `Retry-After`), `key_store_unavailable`, `database_unavailable`, `auth_unavailable`, `playground_unavailable` |

## CORS

Allowed origins come from `ALLOWED_ORIGINS` (comma-separated; `*` matches one DNS label, e.g.
`https://*.vercel.app`). Allowed request headers: `Authorization`, `Content-Type`, `X-Turnstile-Token`,
`X-Request-ID`; the rate-limit headers, `Retry-After` and `X-Request-ID` are exposed to browsers.

## Privacy

Request text and context are never logged or stored. Logs record check names, lengths and latency only. Cached
responses (Redis, 1 h) are keyed by a sha256 of model version, checks, text and context and hold only scores.
