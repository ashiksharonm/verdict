"""Exceptions raised by the client."""

from __future__ import annotations

from typing import Optional


class VerdictError(Exception):
    """Base class for every error the SDK raises on purpose.

    Attributes:
        message: Human-readable description (the API's ``error.message`` when there is one).
        status: HTTP status code, or ``None`` for network errors.
        code: The API's machine-readable ``error.code`` (for example ``"rate_limited"``), if any.
        request_id: The ``X-Request-ID`` response header; quote it when reporting a problem.
        retry_after: Seconds the server asked us to wait (``Retry-After``), if it sent one.
    """

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after

    def __str__(self) -> str:
        parts = []
        if self.status is not None:
            parts.append(f"HTTP {self.status}")
        if self.code:
            parts.append(self.code)
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        suffix = f" [{', '.join(parts)}]" if parts else ""
        return f"{self.message}{suffix}"


class AuthError(VerdictError):
    """401 or 403: the API key is missing, invalid, revoked or not allowed to do this."""


class RateLimitError(VerdictError):
    """429 after retries were exhausted (or the server asked for a wait longer than we allow)."""


class InvalidRequest(VerdictError):
    """Any other 4xx (400, 413, 422, ...): the request was rejected and retrying will not help."""
