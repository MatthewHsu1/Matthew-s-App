"""Per-host token-bucket rate limiter.

Design notes
------------
- Single process-level instance per host; no Redis or distributed state.
- ``acquire(host)`` blocks until a token is available, then consumes one.
- Hosts not in the config map pass through immediately (no limiting).
- Thread-safe via a per-bucket ``threading.Lock``.
- Uses ``time.monotonic`` throughout; wall-clock drift cannot cause spurious
  token grants.

Token-bucket semantics
-----------------------
The bucket holds ``burst`` tokens and refills at ``rate_per_second`` tokens/s.
Tokens accumulate up to ``burst`` while the host is idle, giving a short
burst allowance before steady-state throttling kicks in.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class RateLimit:
    """Rate-limit parameters for a single host."""

    rate_per_second: float
    burst: int


# Defaults used by the process-level limiter.
DEFAULT_LIMITS: dict[str, RateLimit] = {
    "gamma-api.polymarket.com": RateLimit(rate_per_second=30.0, burst=30),
    "clob.polymarket.com": RateLimit(rate_per_second=10.0, burst=10),
}


class _Bucket:
    """Token-bucket for a single host."""

    __slots__ = ("_burst", "_last_refill", "_lock", "_rate_per_second", "_tokens")

    def __init__(self, limit: RateLimit) -> None:
        self._rate_per_second = limit.rate_per_second
        self._burst = float(limit.burst)
        self._tokens = self._burst  # start full
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, then consume one."""
        while True:
            with self._lock:
                now = time.monotonic()

                elapsed = now - self._last_refill

                self._last_refill = now

                self._tokens = min(self._burst, self._tokens + elapsed * self._rate_per_second)

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                
                # How long until the next token arrives?
                deficit = 1.0 - self._tokens
                wait = deficit / self._rate_per_second

            # Release the lock while sleeping so other threads can check.
            time.sleep(wait)


class RateLimiter:
    """Process-level per-host token-bucket rate limiter.

    Parameters
    ----------
    limits:
        Mapping of hostname → ``RateLimit``.  Hosts absent from the map are
        not throttled; ``acquire`` returns immediately for them.
    """

    __slots__ = ("_buckets", "_lock")

    def __init__(self, limits: dict[str, RateLimit] | None = None) -> None:
        resolved = limits if limits is not None else DEFAULT_LIMITS

        self._buckets: dict[str, _Bucket] = {
            host: _Bucket(limit) for host, limit in resolved.items()
        }

        # Protects the bucket dict itself (not individual buckets).
        self._lock = threading.Lock()

    def acquire(self, host: str) -> None:
        """Block until a token is available for *host*, then consume one.

        Hosts not in the configured limits map return immediately.
        """
        bucket = self._buckets.get(host)

        if bucket is None:
            return
        
        bucket.acquire()


# Process-level singleton used by ``request_json``.  Code that needs a custom
# limiter (e.g. tests) should construct a ``RateLimiter`` directly and pass it
# explicitly rather than monkeypatching this.
_default_limiter: RateLimiter = RateLimiter()


def get_default_limiter() -> RateLimiter:
    """Return the process-level default ``RateLimiter`` instance."""
    return _default_limiter
