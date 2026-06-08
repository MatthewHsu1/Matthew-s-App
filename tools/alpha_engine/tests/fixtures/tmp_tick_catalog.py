"""Builds a tmp ParquetDataCatalog with TradeTicks + daily bars for tests.

Extends tmp_catalog.build_tmp_catalog (which only writes Bars). Floor
Trading needs trade prints for spike detection + intraday execution; the
existing scan layer still uses daily bars for setup detection.

Used by test_floor_backtest_smoke.py. Hand-crafted prints follow the
shape needed to deterministically trigger a Day-1 setup on bar 21 + a
down-spike on Day 2 morning so the strategy emits one ENTER_TRANCHE event.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import (
    Bar,
    BarSpecification,
    BarType,
    TradeTick,
)
from nautilus_trader.model.enums import (
    AggregationSource,
    AggressorSide,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.identifiers import (
    InstrumentId,
    Symbol,
    TradeId,
    Venue,
)
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog import ParquetDataCatalog


def _instrument(symbol: str, venue: str) -> Equity:
    return Equity(
        instrument_id=InstrumentId(Symbol(symbol), Venue(venue)),
        raw_symbol=Symbol(symbol),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )


def _daily_bar_type(iid: InstrumentId) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def build_floor_tick_catalog(
    *,
    root: Path,
    symbol: str = "XYZ",
    venue: str = "NASDAQ",
    n_prior_bars: int = 25,
    base_price: float = 100.0,
    base_volume: int = 1_000_000,
) -> ParquetDataCatalog:
    """Build a catalog that triggers exactly one Day-1 setup + down-spike entry.

    Layout:
    - 20 prior daily bars: close=base_price, volume=base_volume, lows steady.
    - Day-1 (bar 21): close=base_price-0.5, low=base_price-0.5,
      volume = 3 * base_volume -> trips heavy-volume + lower-band-touch.
    - Day-2 daily bar: open=base_price-1.0, close=base_price-1.5 (red day).
    - Day-2 trade ticks: 120 seconds of baseline prints at base_price-1.0,
      followed by a 5-second avalanche of prints at base_price-1.5 with 10x
      volume per print. This deterministically fires a DOWN spike.
    - Day-3/4 daily bars: above Day-2 close, no further spikes -- strategy
      will exit on Day-4 default close.
    """
    catalog = ParquetDataCatalog(path=str(root))
    instrument = _instrument(symbol, venue)
    catalog.write_data([instrument])

    bar_type = _daily_bar_type(instrument.id)

    bars: list[Bar] = []
    # `n_prior_bars - 5` baseline bars on consecutive calendar days starting
    # 2026-01-05. Synthetic data, so weekend bars are written too (Day-1 itself
    # lands on Sun 2026-01-25 at the default `n_prior_bars=25`). Nautilus
    # accepts any timestamps; the strategy logic does not gate on weekday.
    day0 = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)  # 16:00 ET = daily close
    for i in range(n_prior_bars - 5):
        ts = int((day0 + timedelta(days=i)).timestamp() * 1e9)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{base_price:.2f}"),
                high=Price.from_str(f"{base_price + 0.1:.2f}"),
                low=Price.from_str(f"{base_price - 0.05:.2f}"),
                close=Price.from_str(f"{base_price:.2f}"),
                volume=Quantity.from_int(base_volume),
                ts_event=ts,
                ts_init=ts,
            )
        )
    # Day-1 trigger bar.
    day1_idx = n_prior_bars - 5
    ts_day1 = int((day0 + timedelta(days=day1_idx)).timestamp() * 1e9)
    bars.append(
        Bar(
            bar_type=bar_type,
            open=Price.from_str(f"{base_price:.2f}"),
            high=Price.from_str(f"{base_price + 0.1:.2f}"),
            low=Price.from_str(f"{base_price - 0.5:.2f}"),
            close=Price.from_str(f"{base_price - 0.5:.2f}"),
            volume=Quantity.from_int(base_volume * 3),
            ts_event=ts_day1,
            ts_init=ts_day1,
        )
    )
    # Day-2 bar: red day (open < Day-1 close, close even lower).
    day2_idx = day1_idx + 1
    ts_day2 = int((day0 + timedelta(days=day2_idx)).timestamp() * 1e9)
    bars.append(
        Bar(
            bar_type=bar_type,
            open=Price.from_str(f"{base_price - 1.0:.2f}"),
            high=Price.from_str(f"{base_price - 0.9:.2f}"),
            low=Price.from_str(f"{base_price - 1.6:.2f}"),
            close=Price.from_str(f"{base_price - 1.5:.2f}"),
            volume=Quantity.from_int(base_volume),
            ts_event=ts_day2,
            ts_init=ts_day2,
        )
    )
    # Day-3 + Day-4: flat above Day-2 close so neither stop nor TP fires.
    for offset, close_price in enumerate([base_price - 1.4, base_price - 1.3]):
        idx = day2_idx + 1 + offset
        ts = int((day0 + timedelta(days=idx)).timestamp() * 1e9)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{close_price + 0.05:.2f}"),
                high=Price.from_str(f"{close_price + 0.1:.2f}"),
                low=Price.from_str(f"{close_price - 0.1:.2f}"),
                close=Price.from_str(f"{close_price:.2f}"),
                volume=Quantity.from_int(base_volume),
                ts_event=ts,
                ts_init=ts,
            )
        )

    catalog.write_data(bars)

    # Build Day-2 trade ticks: baseline + burst.
    # day0 is at 21:00 UTC (16:00 ET close). 09:30 EST open = 14:30 UTC,
    # which is day0 + day2_idx days - 6h30m (NOT - 7h, which lands at 09:00 ET pre-market).
    day2_open_utc = day0 + timedelta(days=day2_idx) - timedelta(hours=6, minutes=30)
    ticks: list[TradeTick] = []
    baseline_price = base_price - 1.0
    burst_price = base_price - 1.5
    # 120 baseline prints, 1 per second, 1000 shares each -> baseline rate = 1000 shares/sec.
    for i in range(120):
        ts = int((day2_open_utc + timedelta(seconds=i)).timestamp() * 1e9)
        ticks.append(
            TradeTick(
                instrument_id=instrument.id,
                price=Price.from_str(f"{baseline_price:.2f}"),
                size=Quantity.from_int(1_000),
                aggressor_side=AggressorSide.NO_AGGRESSOR,
                trade_id=TradeId(f"baseline-{i}"),
                ts_event=ts,
                ts_init=ts,
            )
        )
    # 5 burst prints over 5 seconds, 12000 shares each -> burst rate = 12000/s >= 10x baseline.
    burst_start = day2_open_utc + timedelta(seconds=120)
    for i in range(5):
        ts = int((burst_start + timedelta(seconds=i)).timestamp() * 1e9)
        ticks.append(
            TradeTick(
                instrument_id=instrument.id,
                price=Price.from_str(f"{burst_price:.2f}"),
                size=Quantity.from_int(12_000),
                aggressor_side=AggressorSide.SELLER,
                trade_id=TradeId(f"burst-{i}"),
                ts_event=ts,
                ts_init=ts,
            )
        )
    # Day-2 trickle after burst: enough prints to keep baseline alive for stop checks.
    for i in range(60):
        ts = int((burst_start + timedelta(seconds=10 + i)).timestamp() * 1e9)
        ticks.append(
            TradeTick(
                instrument_id=instrument.id,
                price=Price.from_str(f"{burst_price + 0.1:.2f}"),
                size=Quantity.from_int(1_000),
                aggressor_side=AggressorSide.NO_AGGRESSOR,
                trade_id=TradeId(f"post-burst-{i}"),
                ts_event=ts,
                ts_init=ts,
            )
        )
    catalog.write_data(ticks)

    return catalog
