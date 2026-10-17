"""FastAPI app factory. Dependencies are injectable so tests run without the model or any network."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from . import __version__
from .clients import Redis, Supabase, Turnstile
from .config import Settings, origin_regex
from .errors import ApiError, DbUnavailable, RedisError
from .keys import KeyStore
from .limits import Limiter, ResponseCache, Window, cache_key
from .logs import request_id_var, setup_logging
from .schemas import (
    CHECK_INFO,
    BatchRequest,
    BatchResponse,
    CheckRequest,
    CheckResponse,
    KeyCreate,
    KeyCreated,
    KeyList,
    UsageResponse,
)

log = logging.getLogger("verdict.api")
MAX_BODY = 2_500_000
RID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class Metrics:
    def __init__(self):
        r = self.registry = CollectorRegistry()
        self.requests = Counter("verdict_http_requests_total", "HTTP requests", ["route", "status"], registry=r)
        self.latency = Histogram("verdict_http_request_seconds", "HTTP latency", ["route"], registry=r)
        self.inference = Histogram("verdict_inference_seconds", "Model time per scored request", registry=r,
                                   buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
        self.flagged = Counter("verdict_flagged_total", "Flagged results", ["check"], registry=r)
        self.cache = Counter("verdict_cache_total", "Response cache lookups", ["result"], registry=r)
        self.limited = Counter("verdict_rate_limited_total", "429 responses", ["scope"], registry=r)
        self.ready = Gauge("verdict_model_ready", "1 when the model is loaded", registry=r)


def _err(e: ApiError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status, headers=e.headers)


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") and h[7:].strip() else None


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    return (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")) or "unknown"


def create_app(settings: Settings | None = None, model=None, http: httpx.AsyncClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    setup_logging()
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, send_default_pii=False, traces_sample_rate=0.0)
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk is not installed")
    metrics = Metrics()
    own_http = http is None
    http = http or httpx.AsyncClient(timeout=settings.http_timeout_s)
    redis = Redis(http, settings.redis_url, settings.redis_token)
    limiter = Limiter(redis)
    cache = ResponseCache(redis, settings.cache_ttl_s)
    db = Supabase(http, settings.supabase_url, settings.supabase_anon_key, settings.supabase_service_role_key)
    keystore = KeyStore(db, limiter, settings.key_monthly_quota)
    turnstile = Turnstile(http, settings.turnstile_secret)
    if model is None:
        from .model import ModelService

        model = ModelService(settings)
    waiting = 0

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = [asyncio.create_task(keystore.flush_forever())]
        if not model.ready:
            tasks.append(asyncio.create_task(asyncio.to_thread(model.load)))
        yield
        for t in tasks:
            t.cancel()
        if own_http:
            await http.aclose()

    app = FastAPI(title="Verdict API", version=__version__, lifespan=lifespan,
                  description="Calibrated guardrail checks (pii, toxicity, prompt_injection, grounded). "
                              "See docs/API.md in the repository.")
    app.state.keystore, app.state.model, app.state.metrics = keystore, model, metrics
    exact, regex = origin_regex(settings.allowed_origins)
    app.add_middleware(CORSMiddleware, allow_origins=exact, allow_origin_regex=regex, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "X-Turnstile-Token", "X-Request-ID"],
                       expose_headers=["X-Request-ID", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining",
                                       "X-RateLimit-Reset"], max_age=600)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        rid = rid if RID_RE.match(rid) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        try:
            if int(request.headers.get("content-length") or 0) > MAX_BODY:
                resp: Response = _err(ApiError(413, "payload_too_large", "Request body is too large"))
            else:
                resp = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"path": request.url.path})
            resp = JSONResponse({"error": {"code": "internal_error", "message": "Internal server error"}}, status_code=500)
        dur = time.perf_counter() - t0
        route = getattr(request.scope.get("route"), "path", "unmatched")
        resp.headers["X-Request-ID"] = rid
        metrics.requests.labels(route, str(resp.status_code)).inc()
        metrics.latency.labels(route).observe(dur)
        if route not in ("/healthz", "/metrics"):
            log.info("request", extra={"method": request.method, "path": request.url.path, "status": resp.status_code,
                                       "ms": round(dur * 1000, 1)})
        request_id_var.reset(token)
        return resp

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return _err(e)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(p) for p in x['loc'][1:])}: {x['msg']}" for x in e.errors()[:5])
        return JSONResponse({"error": {"code": "invalid_request", "message": msg}}, status_code=422)

    # ---------------------------------------------------------------- scoring
    async def run_checks(items: list[CheckRequest]) -> list[CheckResponse]:
        nonlocal waiting
        if not model.ready:
            raise ApiError(503, "model_loading", "The model is still loading; retry shortly", {"Retry-After": "5"})
        t0 = time.perf_counter()
        out: list[dict | None] = [None] * len(items)
        keys = [cache_key(model.version, it.checks, it.text, it.context) for it in items]
        for i, k in enumerate(keys):
            out[i] = await cache.get(k)
            metrics.cache.labels("hit" if out[i] else "miss").inc()
        todo = [(i, c) for i, it in enumerate(items) if out[i] is None for c in it.checks]
        if todo:
            if waiting >= settings.max_queue:
                raise ApiError(503, "busy", "The server is busy; retry shortly", {"Retry-After": "2"})
            waiting += 1
            try:
                ti = time.perf_counter()
                verdicts = await asyncio.to_thread(
                    model.score_sync, [(c, items[i].text, items[i].context) for i, c in todo])
                metrics.inference.observe(time.perf_counter() - ti)
            finally:
                waiting -= 1
            fresh: dict[int, dict] = {}
            for (i, c), v in zip(todo, verdicts, strict=True):
                fresh.setdefault(i, {})[c] = {"flagged": v.flagged, "score": round(v.score, 6), "threshold": v.threshold}
                if v.flagged:
                    metrics.flagged.labels(c).inc()
            for i, res in fresh.items():
                out[i] = res
                asyncio.create_task(cache.put(keys[i], res))
        ms = round((time.perf_counter() - t0) * 1000, 2)
        resps = []
        for it, res in zip(items, out, strict=True):
            resps.append(CheckResponse(id="chk_" + uuid.uuid4().hex[:16], model_version=model.version,
                                       results={c: res[c] for c in it.checks}, latency_ms=ms))
            log.info("check", extra={"checks": it.checks, "text_len": len(it.text),
                                     "context_len": len(it.context or ""), "latency_ms": ms})
        return resps

    def limited(w: Window, scope: str) -> ApiError:
        metrics.limited.labels(scope).inc()
        return ApiError(429, "rate_limited" if scope != "quota" else "quota_exceeded",
                        "Rate limit exceeded" if scope != "quota" else "Monthly quota exceeded",
                        {**w.headers(), "Retry-After": str(w.retry_after)})

    async def authenticate(request: Request, cost: int, response: Response) -> None:
        raw = _bearer(request)
        if not raw:
            raise ApiError(401, "missing_api_key", "Send your key as 'Authorization: Bearer vk_...'",
                           {"WWW-Authenticate": "Bearer"})
        if not raw.startswith("vk_"):
            raise ApiError(401, "invalid_api_key", "Invalid API key", {"WWW-Authenticate": "Bearer"})
        try:
            rec = await keystore.lookup(raw)
        except DbUnavailable as e:
            log.warning("key lookup unavailable", extra={"error": str(e)})
            raise ApiError(503, "key_store_unavailable",
                           "API key storage is not available yet (database not initialised or unreachable)") from e
        if rec is None:
            raise ApiError(401, "invalid_api_key", "Invalid or revoked API key", {"WWW-Authenticate": "Bearer"})
        try:  # fail open for authenticated keys: a Redis outage must not take the API down
            w = await limiter.window("key", rec.id, settings.key_rate_per_min, cost)
            if not w.allowed:
                raise limited(w, "rate")
            q = await limiter.quota_window(rec.id, rec.monthly_quota, cost)
            if not q.allowed:
                raise limited(q, "quota")
            response.headers.update(w.headers())
            keystore.mark_used(rec.id)
            asyncio.create_task(_record(rec.id, cost))
        except RedisError as e:
            log.warning("redis unavailable, rate limits skipped for key", extra={"error": str(e)})

    async def _record(key_id: str, cost: int) -> None:
        try:
            await limiter.record(key_id, cost)
        except RedisError as e:
            log.warning("usage not recorded", extra={"error": str(e)})

    @app.post("/v1/check", response_model=CheckResponse, tags=["checks"])
    async def check(body: CheckRequest, request: Request, response: Response):
        await authenticate(request, 1, response)
        return (await run_checks([body]))[0]

    @app.post("/v1/check/batch", response_model=BatchResponse, tags=["checks"])
    async def check_batch(body: BatchRequest, request: Request, response: Response):
        await authenticate(request, len(body.items), response)
        return {"results": await run_checks(body.items)}

    @app.post("/v1/playground/check", response_model=CheckResponse, tags=["playground"])
    async def playground(body: CheckRequest, request: Request, response: Response):
        token = request.headers.get("x-turnstile-token")
        if not token:
            raise ApiError(400, "missing_turnstile_token", "X-Turnstile-Token header is required")
        if not turnstile.configured:
            raise ApiError(503, "playground_unavailable", "Playground is not configured")
        ip = client_ip(request)
        try:  # fail closed: without a working limiter the anonymous endpoint stays shut
            w = await limiter.window("pg", hashlib.sha256(ip.encode()).hexdigest()[:24], settings.playground_rate_per_min)
        except RedisError as e:
            log.error("playground limiter unavailable", extra={"error": str(e)})
            raise ApiError(503, "playground_unavailable", "Playground is temporarily unavailable",
                           {"Retry-After": "30"}) from e
        if not w.allowed:
            raise limited(w, "playground")
        try:
            ok = await turnstile.verify(token, ip)
        except httpx.HTTPError as e:
            raise ApiError(503, "playground_unavailable", "Could not verify the challenge; retry shortly") from e
        if not ok:
            raise ApiError(403, "turnstile_failed", "Challenge verification failed")
        response.headers.update(w.headers())
        return (await run_checks([body]))[0]

    # ---------------------------------------------------------------- keys & usage
    async def user_id(request: Request) -> str:
        jwt = _bearer(request)
        if not jwt or jwt.startswith("vk_"):
            raise ApiError(401, "missing_token", "Send a Supabase access token as 'Authorization: Bearer <token>'")
        try:
            uid = await db.user_from_jwt(jwt)
        except DbUnavailable as e:
            raise ApiError(503, "auth_unavailable", str(e)) from e
        if not uid:
            raise ApiError(401, "invalid_token", "Invalid or expired access token")
        return uid

    async def db_call(coro):
        try:
            return await coro
        except DbUnavailable as e:
            raise ApiError(503, "database_unavailable", str(e)) from e

    @app.post("/v1/keys", response_model=KeyCreated, status_code=201, tags=["keys"])
    async def create_key(body: KeyCreate, request: Request):
        uid = await user_id(request)
        res = await db_call(keystore.create(uid, body.name.strip(), settings.max_keys_per_user))
        if not res:
            raise ApiError(409, "key_limit", f"At most {settings.max_keys_per_user} active keys per account")
        return res

    @app.get("/v1/keys", response_model=KeyList, tags=["keys"])
    async def list_keys(request: Request):
        return {"keys": await db_call(keystore.list(await user_id(request)))}

    @app.delete("/v1/keys/{key_id}", status_code=204, tags=["keys"])
    async def revoke_key(key_id: uuid.UUID, request: Request):
        if not await db_call(keystore.revoke(await user_id(request), str(key_id))):
            raise ApiError(404, "not_found", "No active key with that id")
        return Response(status_code=204)

    @app.get("/v1/usage", response_model=UsageResponse, tags=["keys"])
    async def usage(request: Request):
        return await db_call(keystore.usage(await user_id(request)))

    # ---------------------------------------------------------------- meta
    @app.get("/v1/checks", tags=["meta"])
    async def checks():
        return {"checks": [{"name": k, "description": v, "default": k != "grounded", "requires_context": k == "grounded"}
                           for k, v in CHECK_INFO.items()]}

    @app.get("/healthz", tags=["meta"])
    async def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz", tags=["meta"])
    async def readyz():
        body = {"ready": model.ready, "model_version": model.version, "load_seconds": model.load_seconds}
        if model.error:
            body["error"] = model.error
        return JSONResponse(body, status_code=200 if model.ready else 503)

    @app.get("/metrics", include_in_schema=False)
    async def prom():
        metrics.ready.set(1 if model.ready else 0)
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


def app_factory() -> FastAPI:  # uvicorn --factory verdict_api.app:app_factory
    return create_app()
