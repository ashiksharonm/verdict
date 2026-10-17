from __future__ import annotations


class ApiError(Exception):
    """Rendered as `{"error": {"code", "message"}}` with the given status and headers."""

    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


class RedisError(Exception):
    pass


class DbUnavailable(Exception):
    """Supabase is unreachable, or the tables from supabase/migrations/0001_init.sql do not exist yet."""
