"""Alpaca historical bars source (daily + minute)."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Protocol

import pandas as pd

from alpha_engine.data.registry import data_source


class AlpacaRateLimitError(RuntimeError):
    def __init__(self, retry_after_s: float):
        super().__init__(f"rate limited; retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


class _AlpacaClientProto(Protocol):
    def get_stock_bars(self, request) -> pd.DataFrame: ...


def _make_default_client() -> _AlpacaClientProto:
    """Construct the real alpaca-py client. Reads API keys from env."""
    import os

    from alpaca.data.historical import StockHistoricalDataClient

    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set "
            "(typically via the env's secrets.env)."
        )
    return _AlpacaClientAdapter(StockHistoricalDataClient(api_key=api_key, secret_key=secret_key))


class _AlpacaClientAdapter:
    """Adapts alpaca-py's response objects to our DataFrame schema."""

    def __init__(self, raw):
        self._raw = raw

    def get_stock_bars(self, request):
        result = self._raw.get_stock_bars(request)
        # result.df is a pandas MultiIndex DataFrame; flatten to our schema.
        df = result.df.reset_index()
        df = df.rename(columns={"timestamp": "ts"})
        if df["ts"].dtype.kind == "M":
            df["ts"] = df["ts"].astype("int64")
        return df[["ts", "open", "high", "low", "close", "volume"]]


def _timeframe_for(bar_spec: str):
    from alpaca.data.timeframe import TimeFrame
    spec = bar_spec.upper()
    if "DAY" in spec:
        return TimeFrame.Day
    if "MIN" in spec or "MINUTE" in spec:
        return TimeFrame.Minute
    raise ValueError(f"unsupported bar_spec {bar_spec!r} for AlpacaHistoricalSource")


@data_source("alpaca_historical")
class AlpacaHistoricalSource:
    def __init__(self, client: _AlpacaClientProto | None = None):
        self._client_factory = _make_default_client
        self._client_override = client

    @property
    def _client(self) -> _AlpacaClientProto:
        if self._client_override is not None:
            return self._client_override
        self._client_override = self._client_factory()
        return self._client_override

    def fetch(
        self,
        instrument_id: str,
        bar_spec: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest

        timeframe = _timeframe_for(bar_spec)
        request = StockBarsRequest(
            symbol_or_symbols=[instrument_id],
            timeframe=timeframe,
            start=start,
            end=end,
        )
        try:
            return self._client.get_stock_bars(request)
        except AlpacaRateLimitError as e:
            time.sleep(e.retry_after_s)
            return self._client.get_stock_bars(request)
