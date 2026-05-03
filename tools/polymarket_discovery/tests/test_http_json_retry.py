from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from urllib.error import HTTPError

from polymarket_discovery.net.http_json import (
    MAX_RETRY_AFTER_SECONDS,
    RetrySettings,
    request_json,
)
from polymarket_discovery.net.rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_error(code: int, retry_after: str | None = None) -> HTTPError:
    hdrs = HTTPMessage()
    if retry_after is not None:
        hdrs.add_header("Retry-After", retry_after)
    return HTTPError(url="http://x/", code=code, msg="Error", hdrs=hdrs, fp=None)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


_NO_LIMITER = RateLimiter(limits={})  # empty map → no host throttled


def _retry(max_attempts: int = 3, backoff_seconds: float = 0.5, backoff_factor: float = 2.0) -> RetrySettings:
    return RetrySettings(
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        backoff_factor=backoff_factor,
    )


# ---------------------------------------------------------------------------
# Test: Retry-After: 0 on 429 — server hint honored, never less than exponential
# ---------------------------------------------------------------------------


def test_retry_after_zero_uses_exponential_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry-After: 0 means the server wants no extra delay; we still sleep at
    least the exponential minimum (max(0, exponential))."""
    call_count = 0

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_http_error(429, retry_after="0")
        return _FakeResponse({"ok": True})

    slept: list[float] = []
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    result = request_json(
        url="http://x/",
        timeout_seconds=1.0,
        retry=_retry(max_attempts=2, backoff_seconds=0.5, backoff_factor=2.0),
        limiter=_NO_LIMITER,
    )

    assert result == {"ok": True}
    assert len(slept) == 1
    # attempt=0 → exponential = 0.5 * 2.0**0 = 0.5; retry_after=0 → max(0, 0.5) = 0.5
    assert slept[0] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test: Retry-After: 5 with 2-attempt budget
# ---------------------------------------------------------------------------


def test_retry_after_5_dominates_exponential(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Retry-After: 5 > exponential(attempt=0), the slept value is 5."""
    call_count = 0

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_http_error(429, retry_after="5")
        return _FakeResponse({"ok": True})

    slept: list[float] = []
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    result = request_json(
        url="http://x/",
        timeout_seconds=1.0,
        retry=_retry(max_attempts=2, backoff_seconds=0.5, backoff_factor=2.0),
        limiter=_NO_LIMITER,
    )

    assert result == {"ok": True}
    assert len(slept) == 1
    # retry_after=5 > exponential=0.5 → slept value is 5
    assert slept[0] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Test: unparseable Retry-After falls back to exponential
# ---------------------------------------------------------------------------


def test_unparseable_retry_after_falls_back_to_exponential(monkeypatch: pytest.MonkeyPatch) -> None:
    """A garbage Retry-After value must not raise; exponential backoff is used."""
    call_count = 0

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_http_error(429, retry_after="not-a-date-or-number!!!")
        return _FakeResponse({"ok": True})

    slept: list[float] = []
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    result = request_json(
        url="http://x/",
        timeout_seconds=1.0,
        retry=_retry(max_attempts=2, backoff_seconds=0.5, backoff_factor=2.0),
        limiter=_NO_LIMITER,
    )

    assert result == {"ok": True}
    assert len(slept) == 1
    # No retry_after → pure exponential: 0.5 * 2.0**0 = 0.5
    assert slept[0] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test: Retry-After as HTTP-date ~1 second in the future
# ---------------------------------------------------------------------------


def test_retry_after_http_date_one_second_future(monkeypatch: pytest.MonkeyPatch) -> None:
    """An HTTP-date 1 second in the future must produce a sleep of roughly 1s."""
    future = datetime.now(tz=timezone.utc) + timedelta(seconds=1)
    http_date = format_datetime(future, usegmt=True)

    call_count = 0

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_http_error(429, retry_after=http_date)
        return _FakeResponse({"ok": True})

    slept: list[float] = []
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    result = request_json(
        url="http://x/",
        timeout_seconds=1.0,
        # Use low exponential so retry_after dominates
        retry=_retry(max_attempts=2, backoff_seconds=0.0, backoff_factor=1.0),
        limiter=_NO_LIMITER,
    )

    assert result == {"ok": True}
    assert len(slept) == 1
    assert abs(slept[0] - 1.0) <= 1.5, f"expected ~1s sleep, got {slept[0]}"


# ---------------------------------------------------------------------------
# Test: cap at MAX_RETRY_AFTER_SECONDS
# ---------------------------------------------------------------------------


def test_retry_after_capped_at_maximum(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server asking for more than MAX_RETRY_AFTER_SECONDS must be capped."""
    oversized = str(int(MAX_RETRY_AFTER_SECONDS) + 300)

    call_count = 0

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_http_error(429, retry_after=oversized)
        return _FakeResponse({"ok": True})

    slept: list[float] = []
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    result = request_json(
        url="http://x/",
        timeout_seconds=1.0,
        retry=_retry(max_attempts=2, backoff_seconds=0.0, backoff_factor=1.0),
        limiter=_NO_LIMITER,
    )

    assert result == {"ok": True}
    assert len(slept) == 1
    assert slept[0] == pytest.approx(MAX_RETRY_AFTER_SECONDS)
