"""Tests for retry + circuit breaker."""
import time

import pytest

from enterprise_ai.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)
from enterprise_ai.providers.retry import (
    RetryConfig,
    calculate_backoff,
    is_retryable_error,
    parse_retry_after,
)


# ── RetryConfig / calculate_backoff ──────────────────────────────────────────

def test_backoff_increases_exponentially():
    cfg = RetryConfig(base_delay_ms=1_000, max_delay_ms=60_000, multiplier=2.0, jitter_factor=0.0)
    d1 = calculate_backoff(cfg, attempt=1)
    d2 = calculate_backoff(cfg, attempt=2)
    d3 = calculate_backoff(cfg, attempt=3)
    assert d1 < d2 < d3


def test_backoff_respects_max_delay():
    cfg = RetryConfig(base_delay_ms=10_000, max_delay_ms=15_000, multiplier=2.0, jitter_factor=0.0)
    delay = calculate_backoff(cfg, attempt=5)
    assert delay <= 15.0 + 0.01  # small float margin


def test_backoff_jitter_varies():
    cfg = RetryConfig(base_delay_ms=1_000, jitter_factor=0.25)
    delays = {calculate_backoff(cfg, attempt=1) for _ in range(20)}
    # With jitter, we should not get identical values every time
    assert len(delays) > 1


def test_backoff_first_attempt_near_base():
    cfg = RetryConfig(base_delay_ms=1_000, jitter_factor=0.0)
    delay = calculate_backoff(cfg, attempt=1)
    assert 0.9 <= delay <= 1.1


# ── is_retryable_error ───────────────────────────────────────────────────────

def test_retryable_status_429():
    class FakeError(Exception):
        status_code = 429
    assert is_retryable_error(FakeError(), RetryConfig())


def test_retryable_status_503():
    class FakeError(Exception):
        status_code = 503
    assert is_retryable_error(FakeError(), RetryConfig())


def test_not_retryable_404():
    class FakeError(Exception):
        status_code = 404
    assert not is_retryable_error(FakeError(), RetryConfig())


def test_not_retryable_no_status():
    assert not is_retryable_error(ValueError("oops"), RetryConfig())


def test_retryable_custom_codes():
    class FakeError(Exception):
        status_code = 418
    cfg = RetryConfig(retryable_status_codes=frozenset({418}))
    assert is_retryable_error(FakeError(), cfg)


# ── parse_retry_after ────────────────────────────────────────────────────────

def test_parse_retry_after_integer():
    result = parse_retry_after({"Retry-After": "30"})
    assert result == 30.0


def test_parse_retry_after_float():
    result = parse_retry_after({"Retry-After": "5.5"})
    assert result == 5.5


def test_parse_retry_after_lowercase():
    result = parse_retry_after({"retry-after": "10"})
    assert result == 10.0


def test_parse_retry_after_missing():
    result = parse_retry_after({})
    assert result is None


def test_parse_retry_after_invalid():
    result = parse_retry_after({"Retry-After": "not-a-number-or-date"})
    assert result is None


# ── CircuitBreaker ───────────────────────────────────────────────────────────

def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker("test")
    assert cb.state == CircuitBreakerState.closed


async def test_circuit_breaker_opens_after_threshold():
    cfg = CircuitBreakerConfig(failure_threshold=3)
    cb = CircuitBreaker("test", cfg)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitBreakerState.open


async def test_circuit_breaker_open_raises():
    cfg = CircuitBreakerConfig(failure_threshold=1)
    cb = CircuitBreaker("test", cfg)
    cb.record_failure()

    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(lambda: (_ for _ in ()).throw(AssertionError("should not run")))


async def test_circuit_breaker_closed_calls_fn():
    cb = CircuitBreaker("test")
    result = await cb.call(lambda: _async_return(42))
    assert result == 42


async def test_circuit_breaker_transitions_half_open():
    cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_s=0.01)
    cb = CircuitBreaker("test", cfg)
    cb.record_failure()
    assert cb.state == CircuitBreakerState.open
    time.sleep(0.05)  # wait for reset
    assert cb.state == CircuitBreakerState.half_open


async def test_circuit_breaker_closes_after_successes():
    cfg = CircuitBreakerConfig(failure_threshold=1, success_threshold=2, reset_timeout_s=0.01)
    cb = CircuitBreaker("test", cfg)
    cb.record_failure()
    time.sleep(0.05)
    cb.record_success()  # HALF_OPEN
    cb.record_success()  # closes
    assert cb.state == CircuitBreakerState.closed


async def test_circuit_breaker_reopens_on_half_open_failure():
    cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_s=0.01)
    cb = CircuitBreaker("test", cfg)
    cb.record_failure()
    time.sleep(0.05)
    assert cb.state == CircuitBreakerState.half_open
    cb.record_failure()  # fails in HALF_OPEN → back to OPEN
    assert cb.state == CircuitBreakerState.open


async def test_circuit_breaker_success_resets_failure_count():
    cfg = CircuitBreakerConfig(failure_threshold=3)
    cb = CircuitBreaker("test", cfg)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # resets failure count
    cb.record_failure()
    cb.record_failure()
    # Should not be open yet (count reset to 0, then 2 failures)
    assert cb.state == CircuitBreakerState.closed


# ── helper ───────────────────────────────────────────────────────────────────

async def _async_return(value):
    return value
