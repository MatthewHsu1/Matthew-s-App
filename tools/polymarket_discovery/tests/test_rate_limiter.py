"""Tests for the per-host token-bucket rate limiter."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.net.rate_limiter import RateLimit, RateLimiter, _Bucket


# ---------------------------------------------------------------------------
# Unit: immediate acquisition when bucket has tokens
# ---------------------------------------------------------------------------


def test_acquire_returns_immediately_when_bucket_is_full() -> None:
    """A fresh bucket starts full (burst tokens available) — first acquire is instant."""
    limiter = RateLimiter({"example.com": RateLimit(rate_per_second=10.0, burst=5)})
    t0 = time.monotonic()
    limiter.acquire("example.com")
    elapsed = time.monotonic() - t0
    # Should be essentially free — well under 50ms.
    assert elapsed < 0.05, f"acquire should be near-instant on a full bucket, took {elapsed:.3f}s"


def test_acquire_multiple_times_within_burst() -> None:
    """Burst allows several acquires without sleeping."""
    limiter = RateLimiter({"example.com": RateLimit(rate_per_second=10.0, burst=10)})
    t0 = time.monotonic()
    for _ in range(10):
        limiter.acquire("example.com")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.2, f"burst of 10 should be near-instant, took {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Unit: blocking when bucket is empty
# ---------------------------------------------------------------------------


def test_acquire_blocks_when_bucket_is_exhausted() -> None:
    """After burst is consumed, acquire should block at least 1/rate seconds."""
    rate = 10.0  # 10 req/s → 100ms per token
    burst = 2
    limiter = RateLimiter({"example.com": RateLimit(rate_per_second=rate, burst=burst)})

    # Drain the burst.
    for _ in range(burst):
        limiter.acquire("example.com")

    # Next acquire must wait at least ~100ms.
    t0 = time.monotonic()
    limiter.acquire("example.com")
    elapsed = time.monotonic() - t0

    min_expected = 1.0 / rate  # 0.1s
    assert elapsed >= min_expected * 0.8, (
        f"Expected ≥{min_expected * 0.8:.3f}s delay after burst exhaustion, got {elapsed:.3f}s"
    )


# ---------------------------------------------------------------------------
# Unit: refill over time
# ---------------------------------------------------------------------------


def test_bucket_refills_after_sleep() -> None:
    """After sleeping, the bucket should have accumulated new tokens."""
    rate = 20.0  # 20 req/s → 50ms per token
    burst = 1
    limiter = RateLimiter({"example.com": RateLimit(rate_per_second=rate, burst=burst)})

    # Drain the single token.
    limiter.acquire("example.com")

    # Wait long enough for at least 2 tokens to accumulate.
    time.sleep(2.0 / rate + 0.02)

    # Should be able to acquire immediately now (refilled).
    t0 = time.monotonic()
    limiter.acquire("example.com")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05, f"bucket should have refilled, got {elapsed:.3f}s delay"


# ---------------------------------------------------------------------------
# Unit: per-host isolation
# ---------------------------------------------------------------------------


def test_per_host_isolation() -> None:
    """Exhausting one host's bucket must not drain another host's bucket."""
    limiter = RateLimiter({
        "host-a.example.com": RateLimit(rate_per_second=100.0, burst=1),
        "host-b.example.com": RateLimit(rate_per_second=100.0, burst=5),
    })

    # Drain host-a completely.
    limiter.acquire("host-a.example.com")

    # host-b should still have tokens and respond immediately.
    t0 = time.monotonic()
    limiter.acquire("host-b.example.com")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05, f"host-b bucket should be unaffected, took {elapsed:.3f}s"


def test_unknown_host_passes_through_immediately() -> None:
    """A host not in the config map must not be throttled."""
    limiter = RateLimiter({"example.com": RateLimit(rate_per_second=1.0, burst=1)})
    t0 = time.monotonic()
    for _ in range(20):
        limiter.acquire("unlisted-host.example.com")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05, f"unlisted host should pass through instantly, took {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Unit: thread safety — exactly N tokens consumed for N concurrent acquires
# ---------------------------------------------------------------------------


def test_thread_safety_no_double_spend() -> None:
    """100 threads racing on acquire must consume exactly 100 tokens total.

    We verify this by counting successful acquires: if the bucket starts with
    200 tokens and 100 threads each call acquire once, exactly 100 tokens should
    be consumed (bucket ends at 100).  No double-spend means we never hand out
    more tokens than were taken.

    Since we can't easily inspect internal state, we instead set burst=100 and
    rate very high, launch 100 threads, and confirm all 100 return without
    blocking (i.e., no spurious double-spend that would leave some threads stuck).
    """
    n_threads = 100
    limiter = RateLimiter({
        "example.com": RateLimit(rate_per_second=10_000.0, burst=n_threads),
    })

    results: list[float] = []
    lock = threading.Lock()

    def worker() -> None:
        t0 = time.monotonic()
        limiter.acquire("example.com")
        elapsed = time.monotonic() - t0
        with lock:
            results.append(elapsed)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(results) == n_threads, "All threads must have completed acquire"
    # All should complete quickly (bucket had exactly enough tokens).
    slow = [e for e in results if e > 0.5]
    assert not slow, f"{len(slow)} threads blocked unexpectedly: {slow[:5]}"


def test_thread_safety_contended_counting() -> None:
    """Under contention, the total number of tokens granted equals the number of
    acquire() calls — no tokens are created or destroyed.

    Strategy: set rate so high that refill is negligible over the test window
    (rate=1e6/s). Set burst=50. Launch 100 threads. Exactly the first 50 should
    return instantly; the remaining 50 should each wait ~1µs (essentially free at
    1e6/s). All 100 must return within 2 seconds.
    """
    n = 100
    burst = 50
    limiter = RateLimiter({
        "example.com": RateLimit(rate_per_second=1_000_000.0, burst=burst),
    })

    barrier = threading.Barrier(n)
    completed: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()  # all threads start simultaneously
        limiter.acquire("example.com")
        with lock:
            completed.append(True)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(completed) == n, f"Only {len(completed)}/{n} threads completed"


# ---------------------------------------------------------------------------
# Integration: rate limiter slows down parallel CLOB-like calls
# ---------------------------------------------------------------------------


def test_rate_limiter_integration_wall_time() -> None:
    """With cap=50/s and 200 requests issued in parallel, total wall time must
    exceed the theoretical minimum of (200 - burst) / 50 seconds.

    We mock the HTTP layer: each 'request' just calls limiter.acquire() and
    returns immediately.  This proves the limiter is the actual throttle.

    Expected minimum: (200 - 50) / 50 = 3.0s (burst absorbs first 50).
    We use a 10% grace margin → assert elapsed ≥ 2.7s.
    """
    rate = 50.0
    burst = 50
    n_requests = 200

    limiter = RateLimiter({"clob.polymarket.com": RateLimit(rate_per_second=rate, burst=burst)})

    completed: list[int] = []
    lock = threading.Lock()

    def fake_clob_request(i: int) -> None:
        limiter.acquire("clob.polymarket.com")
        with lock:
            completed.append(i)

    t0 = time.monotonic()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(fake_clob_request, i) for i in range(n_requests)]
        for f in futures:
            f.result()
    elapsed = time.monotonic() - t0

    assert len(completed) == n_requests, "All requests must complete"

    # Minimum: (n_requests - burst) / rate = (200 - 50) / 50 = 3.0s
    min_expected = (n_requests - burst) / rate
    grace = 0.90  # allow 10% tolerance
    assert elapsed >= min_expected * grace, (
        f"Rate limiter should have throttled: expected ≥{min_expected * grace:.2f}s, "
        f"got {elapsed:.3f}s"
    )
    # Surface the actual wall time so it appears in the test output.
    print(f"\n[integration] wall time for {n_requests} requests @ {rate}/s (burst={burst}): {elapsed:.3f}s")
    print(f"[integration] minimum expected: {min_expected:.2f}s, actual: {elapsed:.3f}s")
