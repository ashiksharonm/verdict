"""Synchronous and asynchronous HTTP clients with timeouts and retries."""

from __future__ import annotations

import asyncio
import email.utils
import os
import random
import time
from types import TracebackType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Type, TypeVar

import httpx

from . import __version__
from .errors import AuthError, InvalidRequest, RateLimitError, VerdictError
from .models import CheckResult

DEFAULT_BASE_URL = "https://ashiksharonm--verdict-api.us-east.modal.run"
MAX_BATCH = 32
RETRY_STATUS = frozenset({429, 502, 503, 504})
# Only failures that happen before the request is sent are retried on the network side.
_RETRY_NETWORK = (httpx.ConnectError, httpx.ConnectTimeout)

_C = TypeVar("_C", bound="_Base")


def _payload(text: str, checks: Optional[Sequence[str]], context: Optional[str]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"text": text}
    if checks is not None:
        body["checks"] = list(checks)
    if context is not None:
        body["context"] = context
    return body


def parse_retry_after(value: Optional[str], now: Optional[float] = None) -> Optional[float]:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into seconds, or ``None`` if unusable."""
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        seconds = when.timestamp() - (time.time() if now is None else now)
    if seconds != seconds or seconds in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return max(seconds, 0.0)


def _error_from(r: httpx.Response) -> VerdictError:
    """Map a non-2xx response to the right exception type."""
    try:
        err = r.json()["error"]
        message = str(err.get("message") or r.reason_phrase)
        code = err.get("code")
        code = str(code) if code is not None else None
    except (ValueError, KeyError, TypeError, AttributeError):
        message, code = (r.text[:200] or r.reason_phrase), None
    kw: Dict[str, Any] = {
        "status": r.status_code,
        "code": code,
        "request_id": r.headers.get("x-request-id"),
        "retry_after": parse_retry_after(r.headers.get("retry-after")),
    }
    if r.status_code in (401, 403):
        return AuthError(message, **kw)
    if r.status_code == 429:
        return RateLimitError(message, **kw)
    if 400 <= r.status_code < 500:
        return InvalidRequest(message, **kw)
    return VerdictError(message, **kw)


def _validate_batch(items: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    batch = list(items)
    if not batch:
        raise ValueError("check_batch needs at least one item")
    if len(batch) > MAX_BATCH:
        raise ValueError(f"check_batch takes at most {MAX_BATCH} items, got {len(batch)}; use check_many() to chunk")
    return batch


def _parse_one(data: Any) -> CheckResult:
    try:
        return CheckResult.from_json(data)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise VerdictError(f"unexpected response shape from the API: {type(e).__name__}: {e}") from e


def _parse_batch(data: Any) -> List[CheckResult]:
    try:
        raw = data["results"]
    except (KeyError, TypeError) as e:
        raise VerdictError("unexpected response shape from the API: missing 'results'") from e
    return [_parse_one(d) for d in raw]


def _decode(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError as e:
        raise VerdictError("the API returned a non-JSON response", status=r.status_code,
                           request_id=r.headers.get("x-request-id")) from e


class _Base:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff: float = 0.5,
        max_retry_delay: float = 30.0,
    ) -> None:
        key = api_key or os.environ.get("VERDICT_API_KEY")
        if not key:
            raise AuthError("Pass api_key=... or set VERDICT_API_KEY")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.api_key = key
        self.base_url = (base_url or os.environ.get("VERDICT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.max_retry_delay = max_retry_delay
        self._headers = {
            "Authorization": f"Bearer {key}",
            "User-Agent": f"verdict-guardrails/{__version__}",
            "Accept": "application/json",
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r})"  # never print the key

    def _delay(self, attempt: int, retry_after: Optional[float]) -> float:
        """Wait before retry number ``attempt + 1``: Retry-After if sent, else jittered exponential backoff."""
        if retry_after is not None:
            return retry_after
        return float(self.backoff * (2**attempt) * (0.5 + random.random() / 2))  # noqa: S311 - retry jitter, not crypto

    def _retry_delay(self, attempt: int, err: VerdictError) -> Optional[float]:
        """Seconds to sleep before retrying after a retryable response, or ``None`` to give up."""
        if attempt >= self.max_retries:
            return None
        if err.retry_after is not None and err.retry_after > self.max_retry_delay:
            return None  # e.g. a quota that resets in an hour: fail fast instead of blocking
        return self._delay(attempt, err.retry_after)

    @staticmethod
    def _network_error(e: httpx.TransportError) -> VerdictError:
        if isinstance(e, httpx.TimeoutException):
            return VerdictError(f"request timed out ({type(e).__name__})")
        return VerdictError(f"network error ({type(e).__name__}): {e}")


class Client(_Base):
    """Synchronous client.

    >>> with Client(api_key="vk_...") as client:           # doctest: +SKIP
    ...     client.check("hello", checks=["pii"])["pii"].flagged

    Args:
        api_key: API key; defaults to ``$VERDICT_API_KEY``.
        base_url: API root; defaults to ``$VERDICT_BASE_URL`` then :data:`DEFAULT_BASE_URL`.
        timeout: Per-request timeout in seconds.
        max_retries: Retries after the first attempt for 429/502/503/504 and connection failures.
        backoff: Base delay in seconds for exponential backoff (``backoff * 2**attempt``, jittered 50-100%).
        max_retry_delay: If the server's ``Retry-After`` exceeds this, raise instead of waiting.
        transport: Custom ``httpx`` transport (mainly for tests).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 30.0,
                 max_retries: int = 3, backoff: float = 0.5, max_retry_delay: float = 30.0,
                 transport: Optional[httpx.BaseTransport] = None) -> None:
        super().__init__(api_key, base_url, timeout, max_retries, backoff, max_retry_delay)
        self._http = httpx.Client(base_url=self.base_url, headers=self._headers, timeout=timeout, transport=transport)

    def __enter__(self: _C) -> _C:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException],
                 tb: Optional[TracebackType]) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._http.close()

    def _post(self, path: str, body: Dict[str, Any]) -> Any:
        attempt = 0
        while True:
            try:
                r = self._http.post(path, json=body)
            except _RETRY_NETWORK as e:
                if attempt >= self.max_retries:
                    raise self._network_error(e) from e
                time.sleep(self._delay(attempt, None))
                attempt += 1
                continue
            except httpx.TransportError as e:
                raise self._network_error(e) from e
            if r.status_code < 400:
                return _decode(r)
            err = _error_from(r)
            wait = self._retry_delay(attempt, err) if r.status_code in RETRY_STATUS else None
            if wait is None:
                raise err
            time.sleep(wait)
            attempt += 1

    def check(self, text: str, checks: Optional[Sequence[str]] = None, context: Optional[str] = None) -> CheckResult:
        """Run checks on one text. ``checks`` defaults to the API's default set; ``context`` is the source
        document for the ``grounded`` check."""
        return _parse_one(self._post("/v1/check", _payload(text, checks, context)))

    def check_batch(self, items: Sequence[Mapping[str, Any]]) -> List[CheckResult]:
        """Check 1 to 32 items in one request. Each item is ``{"text": ..., "checks": [...], "context": ...}``.

        Raises ``ValueError`` before sending anything if there are zero or more than 32 items."""
        return _parse_batch(self._post("/v1/check/batch", {"items": _validate_batch(items)}))

    def check_many(self, texts: Sequence[str], checks: Optional[Sequence[str]] = None,
                   context: Optional[str] = None) -> List[CheckResult]:
        """Check any number of texts, split into batches of 32. Results are in input order."""
        out: List[CheckResult] = []
        for i in range(0, len(texts), MAX_BATCH):
            out += self.check_batch([_payload(t, checks, context) for t in texts[i:i + MAX_BATCH]])
        return out


class AsyncClient(_Base):
    """Asynchronous client with the same methods and options as :class:`Client`.

    Use ``async with AsyncClient(...) as client:`` (or call ``await client.aclose()``).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 30.0,
                 max_retries: int = 3, backoff: float = 0.5, max_retry_delay: float = 30.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        super().__init__(api_key, base_url, timeout, max_retries, backoff, max_retry_delay)
        self._http = httpx.AsyncClient(base_url=self.base_url, headers=self._headers, timeout=timeout,
                                       transport=transport)

    async def __aenter__(self: _C) -> _C:
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException],
                        tb: Optional[TracebackType]) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._http.aclose()

    async def _post(self, path: str, body: Dict[str, Any]) -> Any:
        attempt = 0
        while True:
            try:
                r = await self._http.post(path, json=body)
            except _RETRY_NETWORK as e:
                if attempt >= self.max_retries:
                    raise self._network_error(e) from e
                await asyncio.sleep(self._delay(attempt, None))
                attempt += 1
                continue
            except httpx.TransportError as e:
                raise self._network_error(e) from e
            if r.status_code < 400:
                return _decode(r)
            err = _error_from(r)
            wait = self._retry_delay(attempt, err) if r.status_code in RETRY_STATUS else None
            if wait is None:
                raise err
            await asyncio.sleep(wait)
            attempt += 1

    async def check(self, text: str, checks: Optional[Sequence[str]] = None,
                    context: Optional[str] = None) -> CheckResult:
        """Async :meth:`Client.check`."""
        return _parse_one(await self._post("/v1/check", _payload(text, checks, context)))

    async def check_batch(self, items: Sequence[Mapping[str, Any]]) -> List[CheckResult]:
        """Async :meth:`Client.check_batch`."""
        return _parse_batch(await self._post("/v1/check/batch", {"items": _validate_batch(items)}))

    async def check_many(self, texts: Sequence[str], checks: Optional[Sequence[str]] = None,
                         context: Optional[str] = None) -> List[CheckResult]:
        """Async :meth:`Client.check_many`."""
        out: List[CheckResult] = []
        for i in range(0, len(texts), MAX_BATCH):
            out += await self.check_batch([_payload(t, checks, context) for t in texts[i:i + MAX_BATCH]])
        return out
