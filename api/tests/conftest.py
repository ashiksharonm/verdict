"""Fake Redis, Supabase and Turnstile behind one httpx MockTransport, and a fake model."""
from __future__ import annotations

import json
import re
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from verdict_api.app import create_app
from verdict_api.config import Settings
from verdict_api.model import Verdict


class FakeModel:
    ready = True
    error = None
    version = "fake@test"
    load_seconds = 0.0

    def __init__(self):
        self.calls = 0

    def load(self):
        pass

    def score_sync(self, items):
        self.calls += 1
        out = []
        for check, text, _ctx in items:
            hit = {"pii": "@", "toxicity": "idiot", "prompt_injection": "ignore previous", "grounded": "fabricated"}[check]
            out.append(Verdict(hit in text.lower(), 0.9 if hit in text.lower() else 0.1, 0.5))
        return out


class World:
    """In-memory stand-ins for the three external services."""

    def __init__(self):
        self.redis: dict[str, str] = {}
        self.redis_down = False
        self.tables_exist = True
        self.api_keys: list[dict] = []
        self.usage_daily: list[dict] = []
        self.users = {"jwt-alice": "u-alice", "jwt-bob": "u-bob"}
        self.turnstile_ok = True
        self.requests: list[str] = []

    def redis_cmd(self, c):
        op = c[0].upper()
        if op == "INCRBY":
            self.redis[c[1]] = str(int(self.redis.get(c[1], 0)) + int(c[2]))
            return int(self.redis[c[1]])
        if op == "GET":
            return self.redis.get(c[1])
        if op == "SET":
            self.redis[c[1]] = c[2]
            return "OK"
        if op == "EXPIRE":
            return 1
        raise AssertionError(c)

    def handle(self, req: httpx.Request) -> httpx.Response:
        host, path = req.url.host, req.url.path
        self.requests.append(f"{host}{path}")
        if host == "redis.test":
            if self.redis_down:
                return httpx.Response(500)
            body = json.loads(req.content)
            if path == "/pipeline":
                return httpx.Response(200, json=[{"result": self.redis_cmd(c)} for c in body])
            return httpx.Response(200, json={"result": self.redis_cmd(body)})
        if host == "challenges.cloudflare.com":
            return httpx.Response(200, json={"success": self.turnstile_ok})
        if host == "supa.test":
            return self.supabase(req, path)
        raise AssertionError(f"unexpected request to {host}")

    def supabase(self, req, path):
        if path == "/auth/v1/user":
            uid = self.users.get(req.headers["authorization"][7:])
            return httpx.Response(200, json={"id": uid}) if uid else httpx.Response(401, json={})
        if not self.tables_exist:
            return httpx.Response(404, json={"code": "PGRST205", "message": "no table"})
        table = path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(req.url.query.decode()).items()}
        rows = self.api_keys if table == "api_keys" else self.usage_daily

        def match(r):
            for k, v in q.items():
                if k in ("select", "order", "limit", "on_conflict"):
                    continue
                op, _, val = v.partition(".")
                if op == "eq" and str(r.get(k)) != val:
                    return False
                if op == "is" and val == "null" and r.get(k) is not None:
                    return False
                if op == "in" and str(r.get(k)) not in val.strip("()").split(","):
                    return False
                if op == "gte" and str(r.get(k)) < val:
                    return False
            return True

        if req.method == "GET":
            return httpx.Response(200, json=[r for r in rows if match(r)])
        body = json.loads(req.content)
        if req.method == "POST" and table == "api_keys":
            row = {**body, "id": f"00000000-0000-0000-0000-{len(rows):012d}", "created_at": "2026-10-18T00:00:00Z",
                   "revoked_at": None}
            rows.append(row)
            return httpx.Response(201, json=[row])
        if req.method == "POST":  # usage_daily upsert
            for b in body:
                ex = next((r for r in rows if r["key_id"] == b["key_id"] and r["day"] == b["day"]), None)
                ex.update(b) if ex else rows.append(b)
            return httpx.Response(201)
        if req.method == "PATCH":
            hit = [r for r in rows if match(r)]
            for r in hit:
                r.update(body)
            return httpx.Response(200, json=hit)
        raise AssertionError(req.method)


@pytest.fixture
def world():
    return World()


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def settings():
    return Settings(supabase_url="https://supa.test", supabase_anon_key="anon", supabase_service_role_key="svc",
                    redis_url="https://redis.test", redis_token="t", turnstile_secret="s",
                    allowed_origins=("http://localhost:3000", "https://*.vercel.app"), key_rate_per_min=5,
                    key_monthly_quota=8, playground_rate_per_min=3)


@pytest.fixture
def client(world, model, settings):
    http = httpx.AsyncClient(transport=httpx.MockTransport(world.handle))
    with TestClient(create_app(settings, model=model, http=http)) as c:
        yield c


def add_key(world, raw="vk_testkey", quota=8, revoked=False):
    from verdict_api.clients import sha256_hex

    world.api_keys.append({"id": "k1", "user_id": "u-alice", "name": "t", "prefix": raw[:10],
                           "key_hash": sha256_hex(raw), "monthly_quota": quota, "created_at": "x",
                           "revoked_at": "2026-01-01" if revoked else None})
    return {"Authorization": f"Bearer {raw}"}


_ = (re, time)
