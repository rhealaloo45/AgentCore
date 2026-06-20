"""Rate limiter — async token bucket, per provider.

Enforces a requests-per-minute ceiling so a fleet of agents doesn't thrash a
provider's limits. Local providers (Ollama) are skipped — no external limit to honour.

Token-bucket model: the bucket refills at ``rpm/60`` tokens per second up to a
capacity; each request consumes one token, awaiting a refill if the bucket is empty.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """A single async token bucket."""

    def __init__(self, requests_per_minute: int) -> None:
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.capacity = float(requests_per_minute)
        self._tokens = float(requests_per_minute)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now

    async def acquire(self) -> None:
        """Consume one token, waiting for a refill if the bucket is empty."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                deficit = 1 - self._tokens
                await asyncio.sleep(deficit / self.rate)


class RateLimiter:
    """Manages one bucket per provider; skips local providers."""

    _SKIP = {"ollama"}

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def configure(self, provider: str, config: dict | None) -> None:
        """Create a bucket for ``provider`` from a middleware config block."""
        config = config or {}
        if not config.get("enabled") or provider in self._SKIP:
            return
        rpm = int(config.get("requests_per_minute", 60))
        self._buckets[provider] = TokenBucket(rpm)

    async def acquire(self, provider: str) -> None:
        """Wait for a slot on ``provider``'s bucket (no-op if not configured)."""
        bucket = self._buckets.get(provider)
        if bucket is not None:
            await bucket.acquire()

    @property
    def active(self) -> bool:
        return bool(self._buckets)
