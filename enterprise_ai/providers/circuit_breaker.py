from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitBreakerState(Enum):
    closed = "closed"       # normal — calls pass through
    open = "open"           # blocked — too many failures
    half_open = "half_open" # probe — one call let through to test recovery


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Circuit breaker '{name}' is OPEN — provider temporarily unavailable"
        )
        self.name = name


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # consecutive failures before OPEN
    success_threshold: int = 2      # successes in HALF_OPEN before CLOSED
    reset_timeout_s: float = 60.0   # seconds in OPEN before attempting HALF_OPEN


class CircuitBreaker:
    """
    Standard three-state circuit breaker for LLM provider calls.

    Usage:
        cb = CircuitBreaker("anthropic")
        result = await cb.call(lambda: provider.complete(messages))
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.closed
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitBreakerState:
        self._maybe_transition_to_half_open()
        return self._state

    def _maybe_transition_to_half_open(self) -> None:
        if (
            self._state == CircuitBreakerState.open
            and time.monotonic() - self._opened_at >= self._config.reset_timeout_s
        ):
            self._state = CircuitBreakerState.half_open
            self._success_count = 0

    def is_open(self) -> bool:
        self._maybe_transition_to_half_open()
        return self._state == CircuitBreakerState.open

    def record_success(self) -> None:
        self._maybe_transition_to_half_open()
        if self._state == CircuitBreakerState.half_open:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._state = CircuitBreakerState.closed
                self._failure_count = 0
                self._success_count = 0
        elif self._state == CircuitBreakerState.closed:
            self._failure_count = 0

    def record_failure(self) -> None:
        if self._state == CircuitBreakerState.half_open:
            self._state = CircuitBreakerState.open
            self._opened_at = time.monotonic()
            return
        self._failure_count += 1
        if self._failure_count >= self._config.failure_threshold:
            self._state = CircuitBreakerState.open
            self._opened_at = time.monotonic()

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute fn through the circuit breaker. Raises CircuitBreakerOpenError if open."""
        if self.is_open():
            raise CircuitBreakerOpenError(self._name)
        try:
            result = await fn()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
