from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from alpha_engine.data.sources.alpaca_historical import (
    AlpacaHistoricalSource,
    AlpacaRateLimitError,
)


class _FakeAlpacaClient:
    def __init__(self):
        self.calls = []
        self._next = None
        self._raise = None

    def queue(self, df):
        self._next = df

    def raise_next(self, exc):
        self._raise = exc

    def get_stock_bars(self, request):
        self.calls.append(request)
        if self._raise is not None:
            e, self._raise = self._raise, None
            raise e
        return self._next if self._next is not None else pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _bars(n):
    return pd.DataFrame({
        "ts": [i * 86_400_000_000_000 for i in range(n)],
        "open": [100.0] * n,
        "high": [101.0] * n,
        "low": [99.0] * n,
        "close": [100.5] * n,
        "volume": [1000] * n,
    })


def test_daily_spec_fetches_daily(monkeypatch):
    src = AlpacaHistoricalSource(client=_FakeAlpacaClient())
    src._client.queue(_bars(3))
    df = src.fetch(
        instrument_id="AAPL",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    assert len(df) == 3
    assert len(src._client.calls) == 1


def test_minute_spec_fetches_minute():
    src = AlpacaHistoricalSource(client=_FakeAlpacaClient())
    src._client.queue(_bars(60))
    df = src.fetch(
        instrument_id="AAPL",
        bar_spec="1-MIN-LAST",
        start=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc),
    )
    assert len(df) == 60


def test_rate_limit_retries_after_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "alpha_engine.data.sources.alpaca_historical.time.sleep",
        lambda s: sleeps.append(s),
    )
    src = AlpacaHistoricalSource(client=_FakeAlpacaClient())
    src._client.raise_next(AlpacaRateLimitError(retry_after_s=2.0))
    src._client.queue(_bars(1))
    df = src.fetch(
        instrument_id="AAPL",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert len(df) == 1
    assert sleeps == [2.0]


def test_unsupported_bar_spec_raises():
    src = AlpacaHistoricalSource(client=_FakeAlpacaClient())
    with pytest.raises(ValueError, match="unsupported"):
        src.fetch(
            instrument_id="AAPL",
            bar_spec="1-WEEK-LAST",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 8, tzinfo=timezone.utc),
        )
