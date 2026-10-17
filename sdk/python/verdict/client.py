from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import Sequence
from typing import Any

import httpx

from .errors import AuthError, InvalidRequest, RateLimitError, VerdictError
from .models import CheckResult

DEFAULT_BASE_URL = "https://ashiksharon005-verdict-api.hf.space"
RETRY_STATUS = {429, 502, 503, 504}


def _payload(text: str, checks: Sequence[str] | None, context: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"text": text}
    if checks is not None:
        body["checks"] = list(checks)
    if context is not None:
        body["context"] = context
    return body


def _delay(attempt: int, retry_after: str | None, backoff: float) -> float:
    """Seconds to wait: the server's Retry-After when it sends one, else jittered exponential backoff."""
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return backoff * (2 ** attempt) * (0.5 + random.random() / 2)


def _raise_for(r: httpx.Response) -> None:
    try:
        err = r.json()["error"]
        msg, code = err.get("message", r.text), err.get("code")
    except (ValueError, KeyError, TypeError):
        msg, code = r.text[:200], None
    if r.status_code == 401:
        raise AuthError(msg, 401, code)
    if r.status_code == 429:
        ra = r.headers.get("retry-after")
        raise RateLimitError(msg, float(ra) if ra and ra.replace(".", "").isdigit() else None, status=429, code=code)
    if r.status_code < 500 and r.status_code != 503:
        raise InvalidRequest(msg, r.status_code, code)
    raise VerdictError(msg, r.status_code, code)


class _Base:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 30.0,
                 max_retries: int = 3, backoff: float = 0.5):
        self.api_key = api_key or os.environ.get("VERDICT_API_KEY")
        if not self.api_key:
            raise AuthError("Pass api_key=... or set VERDICT_API_KEY")
        self.base_url = (base_url or os.environ.get("VERDICT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries, self.backoff = max_retries, backoff
        self._headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": "verdict-sdk/0.1.0"}
        self._timeout = timeout


class Client(_Base):
    """Synchronous client. `Client(api_key=...).check("text", checks=["pii"])`."""

    def __init__(self, *a, transport: httpx.BaseTransport | None = None, **kw):
        super().__init__(*a, **kw)
        self._http = httpx.Client(base_url=self.base_url, headers=self._headers, timeout=self._timeout, transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        self._http.close()

    def _post(self, path: str, body: dict) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.post(path, json=body)
            except httpx.TransportError as e:
                if attempt == self.max_retries:
                    raise VerdictError(f"network error: {type(e).__name__}") from e
                time.sleep(_delay(attempt, None, self.backoff))
                continue
            if r.status_code < 400:
                return r.json()
            if r.status_code in RETRY_STATUS and attempt < self.max_retries:
                time.sleep(_delay(attempt, r.headers.get("retry-after"), self.backoff))
                continue
            _raise_for(r)
        raise AssertionError("unreachable")

    def check(self, text: str, checks: Sequence[str] | None = None, context: str | None = None) -> CheckResult:
        return CheckResult.from_json(self._post("/v1/check", _payload(text, checks, context)))

    def check_batch(self, items: Sequence[dict[str, Any]]) -> list[CheckResult]:
        """`items` are dicts like `{"text": ..., "checks": [...], "context": ...}`; at most 32 per call."""
        return [CheckResult.from_json(d) for d in self._post("/v1/check/batch", {"items": list(items)})["results"]]

    def check_many(self, texts: Sequence[str], checks: Sequence[str] | None = None,
                   context: str | None = None) -> list[CheckResult]:
        """Check any number of texts, split into batches of 32."""
        out: list[CheckResult] = []
        for i in range(0, len(texts), 32):
            out += self.check_batch([_payload(t, checks, context) for t in texts[i:i + 32]])
        return out


class AsyncClient(_Base):
    """Asynchronous client with the same methods as `Client`."""

    def __init__(self, *a, transport: httpx.AsyncBaseTransport | None = None, **kw):
        super().__init__(*a, **kw)
        self._http = httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=self._timeout,
                                       transport=transport)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _post(self, path: str, body: dict) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                r = await self._http.post(path, json=body)
            except httpx.TransportError as e:
                if attempt == self.max_retries:
                    raise VerdictError(f"network error: {type(e).__name__}") from e
                await asyncio.sleep(_delay(attempt, None, self.backoff))
                continue
            if r.status_code < 400:
                return r.json()
            if r.status_code in RETRY_STATUS and attempt < self.max_retries:
                await asyncio.sleep(_delay(attempt, r.headers.get("retry-after"), self.backoff))
                continue
            _raise_for(r)
        raise AssertionError("unreachable")

    async def check(self, text: str, checks: Sequence[str] | None = None, context: str | None = None) -> CheckResult:
        return CheckResult.from_json(await self._post("/v1/check", _payload(text, checks, context)))

    async def check_batch(self, items: Sequence[dict[str, Any]]) -> list[CheckResult]:
        data = await self._post("/v1/check/batch", {"items": list(items)})
        return [CheckResult.from_json(d) for d in data["results"]]

    async def check_many(self, texts: Sequence[str], checks: Sequence[str] | None = None,
                         context: str | None = None) -> list[CheckResult]:
        out: list[CheckResult] = []
        for i in range(0, len(texts), 32):
            out += await self.check_batch([_payload(t, checks, context) for t in texts[i:i + 32]])
        return out
