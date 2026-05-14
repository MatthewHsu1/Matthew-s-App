"""Builds a tiny in-memory backtest engine + bar stream for tests.

Hides Nautilus's catalog/instrument plumbing from tests so we can swap the
underlying mechanism (synthetic data vs ParquetDataCatalog) without changing
test code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

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


def build_engine_with_synthetic_bars(
    *,
    symbol: str = "MSFT",
    venue: str = "NASDAQ",
    n_bars: int = 10,
    start_price: float = 100.0,
    step: float = 0.5,
) -> Tuple[BacktestEngine, list[InstrumentId]]:
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
