"""Builds a tmp ParquetDataCatalog with handcrafted bars for tests.

Replaces the catalog-side role of the old synthetic_fixture module. Tests use
this when they need a small, deterministic catalog of bars to feed into a
BacktestEngine or Actor.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog import ParquetDataCatalog


_AGGREGATION_BY_NAME = {
    "DAY": BarAggregation.DAY,
    "MINUTE": BarAggregation.MINUTE,
}


def _parse_bar_spec(spec_str: str) -> BarSpecification:
    """Parse '1-DAY-LAST' or '5-MINUTE-LAST' into a BarSpecification."""
    step_str, agg_str, price_str = spec_str.split("-")
    return BarSpecification(
        step=int(step_str),
        aggregation=_AGGREGATION_BY_NAME[agg_str],
        price_type=PriceType[price_str],
    )


def _bar_step_seconds(spec: BarSpecification) -> int:
    if spec.aggregation == BarAggregation.DAY:
        return 86_400 * spec.step
    if spec.aggregation == BarAggregation.MINUTE:
        return 60 * spec.step
    raise ValueError(f"unsupported aggregation {spec.aggregation!r}")


def build_tmp_catalog(
    *,
    root: Path,
    symbol: str = "MSFT",
    venue: str = "NASDAQ",
    bar_spec: str = "1-DAY-LAST",
    start: datetime | None = None,
    n_bars: int = 30,
    start_price: float = 100.0,
    step_price: float = 0.5,
    volume: int = 1_000,
) -> ParquetDataCatalog:
    """Build a ParquetDataCatalog at `root` populated with `n_bars`.

    Prices walk linearly from `start_price` by `step_price` each bar.
    Volumes are constant. Timestamps are evenly spaced by the bar aggregation.
    """
    if start is None:
        start = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)

    catalog = ParquetDataCatalog(path=str(root))

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
    catalog.write_data([instrument])

    spec = _parse_bar_spec(bar_spec)
    bar_type = BarType(
        instrument_id=instrument.id,
        bar_spec=spec,
        aggregation_source=AggregationSource.EXTERNAL,
    )

    step_s = _bar_step_seconds(spec)
    bars: list[Bar] = []
    for i in range(n_bars):
        price = start_price + i * step_price
        ts = int((start + timedelta(seconds=i * step_s)).timestamp() * 1e9)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{price:.2f}"),
                high=Price.from_str(f"{price + 0.1:.2f}"),
                low=Price.from_str(f"{price - 0.1:.2f}"),
                close=Price.from_str(f"{price:.2f}"),
                volume=Quantity.from_int(volume),
                ts_event=ts,
                ts_init=ts,
            )
        )

    catalog.write_data(bars)
    return catalog
