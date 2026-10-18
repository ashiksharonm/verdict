from __future__ import annotations


class VerdictError(Exception):
    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status, self.code = status, code


class AuthError(VerdictError):
    """401: missing, invalid or revoked API key."""


class RateLimitError(VerdictError):
    """429 after retries were exhausted."""

    def __init__(self, message: str, retry_after: float | None = None, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class InvalidRequest(VerdictError):
    """4xx other than 401/429: the request was rejected and retrying will not help."""
