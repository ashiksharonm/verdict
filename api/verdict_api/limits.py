"""Fixed-window rate limits, monthly quota, usage counters and the response cache, on Upstash Redis."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from .clients import Redis, sha256_hex
from .errors import RedisError

log = logging.getLogger("verdict.limits")


@dataclass(frozen=True)
class Window:
    limit: int
    remaining: int
    reset: int  # unix seconds when the window ends
    allowed: bool

    @property
    def retry_after(self) -> int:
        return max(1, self.reset - int(time.time()))

    def headers(self) -> dict[str, str]:
        return {"X-RateLimit-Limit": str(self.limit), "X-RateLimit-Remaining": str(max(0, self.remaining)),
                "X-RateLimit-Reset": str(self.reset)}


def month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m")


def day_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def next_month_start(now: datetime | None = None) -> int:
    n = now or datetime.now(UTC)
    y, m = (n.year + 1, 1) if n.month == 12 else (n.year, n.month + 1)
    return int(datetime(y, m, 1, tzinfo=UTC).timestamp())


class Limiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def window(self, scope: str, ident: str, limit: int, cost: int = 1, seconds: int = 60) -> Window:
        """Count `cost` requests in the current window. Raises RedisError if Redis is unavailable."""
        now = int(time.time())
        idx = now // seconds
        key = f"rl:{scope}:{ident}:{idx}"
        count, _ = await self.redis.pipeline([["INCRBY", key, cost], ["EXPIRE", key, seconds * 2]])
        count = int(count)
        return Window(limit, limit - count, (idx + 1) * seconds, count <= limit)

    async def month_used(self, key_id: str) -> int:
        v = await self.redis.cmd("GET", f"q:{key_id}:{month_key()}")
        return int(v or 0)

    async def quota_window(self, key_id: str, quota: int, cost: int) -> Window:
        used = await self.month_used(key_id)
        return Window(quota, quota - used - cost, next_month_start(), used + cost <= quota)

    async def record(self, key_id: str, cost: int) -> None:
        mk, dk = f"q:{key_id}:{month_key()}", f"u:{key_id}:{day_key()}"
        await self.redis.pipeline([["INCRBY", mk, cost], ["EXPIRE", mk, 35 * 86400],
                                   ["INCRBY", dk, cost], ["EXPIRE", dk, 40 * 86400]])

    async def day_count(self, key_id: str, day: str) -> int:
        return int(await self.redis.cmd("GET", f"u:{key_id}:{day}") or 0)

    async def month_counts(self, key_ids: list[str]) -> dict[str, int]:
        if not key_ids:
            return {}
        vals = await self.redis.pipeline([["GET", f"q:{k}:{month_key()}"] for k in key_ids])
        return {k: int(v or 0) for k, v in zip(key_ids, vals, strict=True)}


def cache_key(model_version: str, checks: list[str], text: str, context: str | None) -> str:
    return "c:" + sha256_hex(json.dumps([model_version, sorted(checks), text, context], ensure_ascii=False))


class ResponseCache:
    def __init__(self, redis: Redis, ttl_s: int):
        self.redis, self.ttl = redis, ttl_s

    async def get(self, key: str) -> dict | None:
        try:
            v = await self.redis.cmd("GET", key)
            return json.loads(v) if v else None
        except (RedisError, ValueError):
            return None

    async def put(self, key: str, results: dict) -> None:
        try:
            await self.redis.cmd("SET", key, json.dumps(results), "EX", self.ttl)
        except RedisError:
            pass
