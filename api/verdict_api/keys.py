"""API key and usage store (Supabase) with a short in-process lookup cache."""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .clients import Supabase, sha256_hex
from .errors import DbUnavailable, RedisError
from .limits import Limiter, day_key

log = logging.getLogger("verdict.keys")
LOOKUP_TTL_S = 60  # a revoked key keeps working at most this long on this instance
NEG_TTL_S = 30


@dataclass(frozen=True)
class KeyRecord:
    id: str
    user_id: str
    monthly_quota: int


class KeyStore:
    def __init__(self, db: Supabase, limiter: Limiter, default_quota: int):
        self.db, self.limiter, self.default_quota = db, limiter, default_quota
        self._cache: dict[str, tuple[float, KeyRecord | None]] = {}
        self._dirty: set[tuple[str, str]] = set()

    async def lookup(self, raw_key: str) -> KeyRecord | None:
        h = sha256_hex(raw_key)
        hit = self._cache.get(h)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        rows = await self.db.rest("GET", "api_keys", params={
            "key_hash": f"eq.{h}", "select": "id,user_id,monthly_quota,revoked_at", "limit": "1"})
        rec = None
        if rows and not rows[0].get("revoked_at"):
            r = rows[0]
            rec = KeyRecord(r["id"], r["user_id"], int(r["monthly_quota"]))
        if len(self._cache) > 5000:
            self._cache.clear()
        self._cache[h] = (time.monotonic() + (LOOKUP_TTL_S if rec else NEG_TTL_S), rec)
        return rec

    def mark_used(self, key_id: str) -> None:
        self._dirty.add((key_id, day_key()))

    async def create(self, user_id: str, name: str, max_keys: int) -> dict:
        active = await self.db.rest("GET", "api_keys", params={
            "user_id": f"eq.{user_id}", "revoked_at": "is.null", "select": "id"})
        if len(active) >= max_keys:
            return {}
        raw = "vk_" + secrets.token_urlsafe(32)
        rows = await self.db.rest("POST", "api_keys", prefer="return=representation", body={
            "user_id": user_id, "name": name, "prefix": raw[:10], "key_hash": sha256_hex(raw),
            "monthly_quota": self.default_quota})
        r = rows[0]
        return {"id": r["id"], "key": raw, "prefix": r["prefix"], "name": r["name"], "created_at": r["created_at"]}

    async def list(self, user_id: str) -> list[dict]:
        return await self.db.rest("GET", "api_keys", params={
            "user_id": f"eq.{user_id}", "order": "created_at.desc",
            "select": "id,name,prefix,created_at,revoked_at,monthly_quota"})

    async def revoke(self, user_id: str, key_id: str) -> bool:
        rows = await self.db.rest("PATCH", "api_keys", prefer="return=representation", params={
            "id": f"eq.{key_id}", "user_id": f"eq.{user_id}", "revoked_at": "is.null"},
            body={"revoked_at": datetime.now(UTC).isoformat()})
        self._cache.clear()
        return bool(rows)

    async def usage(self, user_id: str) -> dict:
        keys = await self.list(user_id)
        ids = [k["id"] for k in keys]
        today = day_key()
        since = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
        days: dict[str, int] = {}
        if ids:
            rows = await self.db.rest("GET", "usage_daily", params={
                "key_id": f"in.({','.join(ids)})", "day": f"gte.{since}", "select": "key_id,day,count"})
            for r in rows:
                days[r["day"]] = days.get(r["day"], 0) + int(r["count"])
        month_prefix = today[:7]
        db_month = {k: 0 for k in ids}
        if ids:
            for r in rows:
                if r["day"].startswith(month_prefix):
                    db_month[r["key_id"]] += int(r["count"])
        try:  # live counters are fresher than the periodically flushed table
            live = await self.limiter.month_counts(ids)
            today_live = sum([await self.limiter.day_count(i, today) for i in ids])
            if today_live:
                days[today] = max(days.get(today, 0), today_live)
        except RedisError:
            live = {}
        month = {k: max(db_month[k], live.get(k, 0)) for k in ids}
        active = [k for k in keys if not k.get("revoked_at")]
        return {
            "month": month_prefix, "month_total": sum(month.values()),
            "quota": active[0]["monthly_quota"] if active else self.default_quota,
            "days": [{"day": d, "count": c} for d, c in sorted(days.items())],
            "keys": [{"id": k["id"], "name": k["name"], "prefix": k["prefix"], "month_count": month[k["id"]],
                      "quota": k["monthly_quota"]} for k in keys if not k.get("revoked_at")],
        }

    async def flush(self) -> None:
        """Upsert today's Redis counters into usage_daily (absolute values, so retries are idempotent)."""
        pending, self._dirty = self._dirty, set()
        rows = []
        try:
            for key_id, day in pending:
                rows.append({"key_id": key_id, "day": day, "count": await self.limiter.day_count(key_id, day)})
            if rows:
                await self.db.rest("POST", "usage_daily", params={"on_conflict": "key_id,day"},
                                   prefer="resolution=merge-duplicates", body=rows)
        except (RedisError, DbUnavailable) as e:
            self._dirty |= pending
            log.warning("usage flush failed", extra={"error": str(e)})

    async def flush_forever(self, every_s: int = 60) -> None:
        while True:
            await asyncio.sleep(every_s)
            if self._dirty:
                await self.flush()
