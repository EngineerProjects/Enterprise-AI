from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class RetryConfig:
    """
    Configuration for provider call retries with exponential backoff.

    Usage:
        agent = Agent(
            provider=create_provider("anthropic"),
            retry_config=RetryConfig(max_attempts=4),
        )
    """

    max_attempts: int = 3
    base_delay_ms: int = 1_000       # 1 s initial delay
    max_delay_ms: int = 60_000       # 60 s cap
    multiplier: float = 2.0
    jitter_factor: float = 0.25      # ±25 % random jitter
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )


def calculate_backoff(config: RetryConfig, attempt: int) -> float:
    """
    Return delay in seconds for the given attempt (1-indexed).
    Applies exponential growth + jitter.
    """
    delay_ms = float(config.base_delay_ms)
    for _ in range(attempt - 1):
        delay_ms = min(delay_ms * config.multiplier, float(config.max_delay_ms))

    jitter = delay_ms * config.jitter_factor * (random.random() * 2 - 1)
    delay_ms = max(0.0, delay_ms + jitter)
    return delay_ms / 1000.0


def is_retryable_error(exc: Exception, config: RetryConfig) -> bool:
    """Return True if the exception represents a transient error worth retrying."""
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return int(status_code) in config.retryable_status_codes

    # Network-level errors (httpx)
    try:
        import httpx
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return True
    except ImportError:
        pass

    return False


def parse_retry_after(headers: dict[str, str]) -> float | None:
    """
    Parse the Retry-After response header.
    Accepts integer seconds or HTTP-date format.
    Returns delay in seconds, or None if header absent / unparseable.
    """
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())
    except Exception:
        return None
