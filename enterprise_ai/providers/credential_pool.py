"""
Credential pool — round-robin rotation of API keys on rate-limit (429).

Usage (providers handle this internally):
    pool = CredentialPool(["sk-1", "sk-2", "sk-3"])
    pool.reset_round()
    while True:
        try:
            return await client_for(pool.current).call(...)
        except RateLimitError:
            if pool.rotate():   # True = all keys exhausted this round
                raise           # let the loop's retry+backoff handle it
            # else: loop again with the next key

Key design choices:
- rotate() only on 429 (rate limit). 5xx errors should not rotate keys.
- After rotate() returns True the error bubbles to the loop, which applies
  exponential backoff and eventually tries the fallback provider.
- reset_round() must be called at the start of every new request so each
  key gets a fresh chance.
"""
from __future__ import annotations


class CredentialPool:
    def __init__(self, keys: list[str | None]) -> None:
        if not keys:
            raise ValueError("CredentialPool requires at least one key")
        self._keys = list(keys)
        self._idx: int = 0
        self._tries: int = 0

    @property
    def current(self) -> str | None:
        return self._keys[self._idx]

    @property
    def size(self) -> int:
        return len(self._keys)

    def rotate(self) -> bool:
        """
        Advance to the next key.
        Returns True when every key has been tried this round (pool exhausted).
        """
        self._tries += 1
        if self._tries >= self._size:
            return True
        self._idx = (self._idx + 1) % self._size
        return False

    def reset_round(self) -> None:
        """Call at the start of each new provider request."""
        self._tries = 0

    # Internal alias used by rotate()
    @property
    def _size(self) -> int:
        return len(self._keys)
