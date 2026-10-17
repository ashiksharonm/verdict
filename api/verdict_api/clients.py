"""Thin async clients for Upstash Redis (REST), Supabase (PostgREST + GoTrue) and Cloudflare Turnstile."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx

from .errors import DbUnavailable, RedisError

log = logging.getLogger("verdict.clients")

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class Redis:
    def __init__(self, http: httpx.AsyncClient, url: str, token: str):
        self.http, self.url, self.token = http, url, token

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    async def _post(self, path: str, body: Any) -> Any:
        if not self.configured:
            raise RedisError("redis not configured")
        try:
            r = await self.http.post(self.url + path, json=body, headers={"Authorization": f"Bearer {self.token}"})
        except httpx.HTTPError as e:
            raise RedisError(f"redis unreachable: {type(e).__name__}") from e
        if r.status_code != 200:
            raise RedisError(f"redis HTTP {r.status_code}")
        return r.json()

    async def cmd(self, *args: Any) -> Any:
        data = await self._post("", [str(a) for a in args])
        if "error" in data:
            raise RedisError(data["error"])
        return data.get("result")

    async def pipeline(self, cmds: list[list[Any]]) -> list[Any]:
        data = await self._post("/pipeline", [[str(a) for a in c] for c in cmds])
        out = []
        for item in data:
            if item.get("error"):
                raise RedisError(item["error"])
            out.append(item.get("result"))
        return out


class Supabase:
    """Server-side access with the service role key (bypasses RLS) plus JWT verification."""

    def __init__(self, http: httpx.AsyncClient, url: str, anon_key: str, service_key: str):
        self.http, self.url, self.anon_key, self.service_key = http, url, anon_key, service_key

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_key)

    def _headers(self, **extra: str) -> dict[str, str]:
        return {"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}", **extra}

    async def rest(self, method: str, table: str, *, params: dict[str, str] | None = None, body: Any = None,
                   prefer: str | None = None) -> list[dict]:
        if not self.configured:
            raise DbUnavailable("Supabase is not configured on the server")
        headers = self._headers(**({"Prefer": prefer} if prefer else {}), **{"Content-Type": "application/json"})
        try:
            r = await self.http.request(method, f"{self.url}/rest/v1/{table}", params=params,
                                        content=json.dumps(body) if body is not None else None, headers=headers)
        except httpx.HTTPError as e:
            raise DbUnavailable(f"Supabase unreachable: {type(e).__name__}") from e
        if r.status_code >= 400:
            code = ""
            try:
                code = r.json().get("code", "")
            except ValueError:
                pass
            if r.status_code == 404 or code in {"PGRST205", "42P01", "PGRST200"}:
                raise DbUnavailable("Supabase tables are missing; apply supabase/migrations/0001_init.sql")
            log.warning("supabase error", extra={"status": r.status_code, "table": table, "code": code})
            raise DbUnavailable(f"Supabase error {r.status_code}")
        return r.json() if r.content else []

    async def user_from_jwt(self, jwt: str) -> str | None:
        """The auth.users id for a Supabase access token, or None if the token is invalid."""
        if not (self.url and self.anon_key):
            raise DbUnavailable("Supabase auth is not configured on the server")
        try:
            r = await self.http.get(f"{self.url}/auth/v1/user",
                                    headers={"apikey": self.anon_key, "Authorization": f"Bearer {jwt}"})
        except httpx.HTTPError as e:
            raise DbUnavailable(f"Supabase auth unreachable: {type(e).__name__}") from e
        if r.status_code in (401, 403):
            return None
        if r.status_code != 200:
            raise DbUnavailable(f"Supabase auth error {r.status_code}")
        return r.json().get("id")


class Turnstile:
    def __init__(self, http: httpx.AsyncClient, secret: str):
        self.http, self.secret = http, secret

    @property
    def configured(self) -> bool:
        return bool(self.secret)

    async def verify(self, token: str, ip: str | None) -> bool:
        """True when Cloudflare accepts the token. Raises httpx.HTTPError if siteverify is unreachable."""
        data = {"secret": self.secret, "response": token}
        if ip:
            data["remoteip"] = ip
        r = await self.http.post(SITEVERIFY_URL, data=data)
        r.raise_for_status()
        return bool(r.json().get("success"))
