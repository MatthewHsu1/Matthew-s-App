from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from alpha_engine.data.sources.ibkr_historical import (
    IbkrHistoricalSource,
    IbkrPacingViolation,
)


class _FakeClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._next_response: pd.DataFrame | None = None
        self._raise = None

    def queue_response(self, df: pd.DataFrame):
        self._next_response = df

    def raise_next(self, exc: Exception):
        self._raise = exc

    def historical_bars(self, *, instrument_id, bar_spec, start, end):
        self.calls.append(dict(
            instrument_id=instrument_id, bar_spec=bar_spec, start=start, end=end
        ))
        if self._raise is not None:
            e, self._raise = self._raise, None
            raise e
        if self._next_response is not None:
            r, self._next_response = self._next_response, None
            return r
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _bars(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": [i * 86_400_000_000_000 for i in range(n)],
        "open": [100.0] * n,
        "high": [101.0] * n,
        "low": [99.0] * n,
        "close": [100.5] * n,
        "volume": [1000] * n,
    })


def test_fetch_returns_dataframe_with_schema():
    src = IbkrHistoricalSource(client=_FakeClient())
    src._client.queue_response(_bars(3))
    df = src.fetch(
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    assert len(df) == 3
    assert set(df.columns) == {"ts", "open", "high", "low", "close", "volume"}


def test_fetch_retries_after_pacing_violation(monkeypatch):
    """On PacingViolation, sleep 60s then retry once."""
    sleeps: list[float] = []
    monkeypatch.setattr(
        "alpha_engine.data.sources.ibkr_historical.time.sleep",
        lambda s: sleeps.append(s),
    )

    src = IbkrHistoricalSource(client=_FakeClient())
    src._client.raise_next(IbkrPacingViolation("too fast"))
    src._client.queue_response(_bars(2))

    df = src.fetch(
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert len(df) == 2
    assert sleeps == [60.0]


def test_fetch_propagates_after_retry_still_fails(monkeypatch):
    monkeypatch.setattr(
        "alpha_engine.data.sources.ibkr_historical.time.sleep", lambda s: None
    )
    src = IbkrHistoricalSource(client=_FakeClient())
    src._client.raise_next(IbkrPacingViolation("1"))
    # Second call also raises.
    def _again(*a, **kw):
        raise IbkrPacingViolation("2")
    src._client.historical_bars = _again  # type: ignore[method-assign]
    with pytest.raises(IbkrPacingViolation):
        src.fetch(
            instrument_id="AAPL.NASDAQ",
            bar_spec="1-DAY-LAST",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
