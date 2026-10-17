"""Settings, read once from the environment (see api/.env.example)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


@dataclass(frozen=True)
class Settings:
    model_repo: str = "ashiksharon005/verdict-laya"
    model_dir: str | None = None  # local checkpoint dir (overrides the Hub download)
    onnx_path: str | None = None
    max_len: int = 512
    max_queue: int = 32  # requests allowed to wait for the model before answering 503
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    redis_url: str = ""
    redis_token: str = ""
    turnstile_secret: str = ""
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    key_rate_per_min: int = 60
    key_monthly_quota: int = 10_000
    playground_rate_per_min: int = 10
    max_keys_per_user: int = 5
    cache_ttl_s: int = 3600
    sentry_dsn: str = ""
    http_timeout_s: float = 5.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        e = os.environ.get
        origins = tuple(o.strip() for o in (e("ALLOWED_ORIGINS") or "http://localhost:3000").split(",") if o.strip())
        return cls(
            model_repo=e("VERDICT_MODEL_REPO") or cls.model_repo,
            model_dir=e("VERDICT_MODEL_DIR") or None,
            onnx_path=e("VERDICT_ONNX_PATH") or None,
            max_len=_int("VERDICT_MAX_LEN", 512),
            max_queue=_int("VERDICT_MAX_QUEUE", 32),
            supabase_url=(e("SUPABASE_URL") or "").rstrip("/"),
            supabase_anon_key=e("SUPABASE_ANON_KEY") or "",
            supabase_service_role_key=e("SUPABASE_SERVICE_ROLE_KEY") or "",
            redis_url=(e("UPSTASH_REDIS_REST_URL") or "").rstrip("/"),
            redis_token=e("UPSTASH_REDIS_REST_TOKEN") or "",
            turnstile_secret=e("TURNSTILE_SECRET_KEY") or "",
            allowed_origins=origins,
            key_rate_per_min=_int("KEY_RATE_PER_MIN", 60),
            key_monthly_quota=_int("KEY_MONTHLY_QUOTA", 10_000),
            playground_rate_per_min=_int("PLAYGROUND_RATE_PER_MIN", 10),
            cache_ttl_s=_int("CACHE_TTL_S", 3600),
            sentry_dsn=e("SENTRY_DSN") or "",
        )


def origin_regex(origins: tuple[str, ...]) -> tuple[list[str], str | None]:
    """Split an allowlist into exact origins and one regex for `*` patterns (`https://*.vercel.app`)."""
    exact, patterns = [], []
    for o in origins:
        if "*" in o:
            patterns.append(re.escape(o).replace(r"\*", "[A-Za-z0-9-]+"))
        else:
            exact.append(o)
    return exact, ("^(" + "|".join(patterns) + ")$" if patterns else None)
