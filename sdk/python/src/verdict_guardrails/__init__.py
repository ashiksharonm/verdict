"""Python client for the Verdict guardrail API (PII, toxicity, prompt injection, groundedness)."""

from __future__ import annotations

__version__ = "0.1.0"

from .client import DEFAULT_BASE_URL, AsyncClient, Client  # noqa: E402
from .errors import AuthError, InvalidRequest, RateLimitError, VerdictError  # noqa: E402
from .gate import assert_checks, flag_rates  # noqa: E402
from .models import CheckResult, Verdict  # noqa: E402

__all__ = [
    "DEFAULT_BASE_URL",
    "AsyncClient",
    "AuthError",
    "CheckResult",
    "Client",
    "InvalidRequest",
    "RateLimitError",
    "Verdict",
    "VerdictError",
    "__version__",
    "assert_checks",
    "flag_rates",
]
