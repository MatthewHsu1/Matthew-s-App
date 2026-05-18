"""Builds a tiny in-memory backtest engine + bar stream for tests.

Hides Nautilus's catalog/instrument plumbing from tests so we can swap the
underlying mechanism (synthetic data vs ParquetDataCatalog) without changing
test code.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AccountType,
    AggregationSource,
    BarAggregation,
    OmsType,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money, Price, Quantity

from alpha_engine.data.registry import data_source


def build_engine_with_synthetic_bars(
    *,
    symbol: str = "MSFT",
    venue: str = "NASDAQ",
    n_bars: int = 10,
    start_price: float = 100.0,
    step: float = 0.5,
) -> tuple[BacktestEngine, list[InstrumentId]]:
    """Return (engine, [instrument_id]) populated with `n_bars` 1-minute bars."""
    v = Venue(venue)
    instrument = Equity(
        instrument_id=InstrumentId(Symbol(symbol), v),
        raw_symbol=Symbol(symbol),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )

    config = BacktestEngineConfig(trader_id="ALPHA-001-TEST")
    engine = BacktestEngine(config=config)
    # In Nautilus 1.226.0 add_venue requires OmsType/AccountType enums and
    # starting_balances as list[Money] (not list[str]).
    engine.add_venue(
        venue=v,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
    )
    engine.add_instrument(instrument)

    spec = BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST)
    bar_type = BarType(
        instrument_id=instrument.id,
        bar_spec=spec,
        aggregation_source=AggregationSource.EXTERNAL,
    )

    base_ts = int(datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)
    bars = []
    for i in range(n_bars):
        price = start_price + i * step
        ts = base_ts + i * 60_000_000_000
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{price:.2f}"),
                high=Price.from_str(f"{price + 0.1:.2f}"),
                low=Price.from_str(f"{price - 0.1:.2f}"),
                close=Price.from_str(f"{price:.2f}"),
                volume=Quantity.from_int(1000),
                ts_event=ts,
                ts_init=ts,
            )
        )
    engine.add_data(bars)
    return engine, [instrument.id]


@data_source("synthetic_fixture")
class SyntheticFixtureSource:
    """Deterministic bars for tests and Phase 1 backtests.

    Generates a sinusoidal price path with constant volume. The same
    (instrument_id, bar_spec, start, end) always returns identical data.
    """

    def fetch(
        self,
        instrument_id: str,
        bar_spec: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        if end <= start:
            return _empty_bars()
        # 1 row per day for daily specs; 1 row per minute for minute specs.
        if "DAY" in bar_spec.upper():
            ts_index = pd.date_range(start=start, end=end, freq="1D", tz="UTC")
        elif "MIN" in bar_spec.upper():
            ts_index = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
        else:
            raise ValueError(f"synthetic_fixture: unsupported bar_spec {bar_spec!r}")

        # Deterministic price path seeded by instrument_id.
        seed = sum(ord(c) for c in instrument_id) % 1000
        rng = np.random.default_rng(seed)
        n = len(ts_index)
        base = 100.0 + rng.standard_normal(n).cumsum() * 0.5
        close = base
        open_ = np.r_[close[:1], close[:-1]]
        high = np.maximum(open_, close) + 0.5
        low = np.minimum(open_, close) - 0.5

        return pd.DataFrame({
            "ts": ts_index.view("int64"),  # int64 ns
            "open": open_.astype("float64"),
            "high": high.astype("float64"),
            "low": low.astype("float64"),
            "close": close.astype("float64"),
            "volume": np.full(n, 1000, dtype="int64"),
        })


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame({
        "ts": pd.Series([], dtype="int64"),
        "open": pd.Series([], dtype="float64"),
        "high": pd.Series([], dtype="float64"),
        "low": pd.Series([], dtype="float64"),
        "close": pd.Series([], dtype="float64"),
        "volume": pd.Series([], dtype="int64"),
    })
