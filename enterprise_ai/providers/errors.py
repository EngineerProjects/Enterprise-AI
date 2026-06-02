"""
Error classification for provider calls.

Three classes determine retry/fallback behaviour in the query loop:

    TRANSIENT  → retry with backoff (429, 5xx, network, timeout)
    FALLBACK   → skip retry, try fallback provider (4xx auth/schema)
    FATAL      → raise immediately, no retry, no fallback (404, 410, …)
"""
from __future__ import annotations

from enum import Enum


class ErrorClass(Enum):
    TRANSIENT = "transient"
    FALLBACK = "fallback"
    FATAL = "fatal"


def classify_error(exc: Exception) -> ErrorClass:
    """Map an exception to its error class."""
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        code = int(status_code)
        if code == 429 or 500 <= code < 600:
            return ErrorClass.TRANSIENT
        if code in (400, 401, 403):
            # Auth errors and bad-request (schema mismatch) — try fallback model
            return ErrorClass.FALLBACK
        # 404, 410, other 4xx — nothing will fix this
        return ErrorClass.FATAL

    # Network-level errors (httpx)
    try:
        import httpx
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return ErrorClass.TRANSIENT
    except ImportError:
        pass

    # Unknown exception — treat as transient (safe default: retry)
    return ErrorClass.TRANSIENT
