"""Build a BacktestEngine populated with bars from the HistoricalDataCache.

This module is the bridge between the Parquet historical cache (which knows
how to call out to Alpaca/IBKR/etc.) and Nautilus's BacktestEngine. The
synthetic-fixture path lives in `alpha_engine.data.sources.synthetic_fixture`;
this loader is for real historical sources (Phase 2.1+).

NOTE on bar specs (Caveat #4 from the task spec):
    The bband_volume_setup strategy needs both DAILY and MINUTE streams.
    We load `1-DAY-LAST` and `1-MINUTE-LAST`. The current Alpaca source's
    `_timeframe_for` returns TimeFrame.Minute regardless of step prefix, so
    multi-minute specs (e.g. `5-MIN-LAST`) are not yet supported end-to-end.
    Env configs that need 5-min bars must set `minute_bar_step: 1` until the
    Alpaca source learns to honor multi-minute steps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import pandas as pd

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import EnvConfig
from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import default_registry
import alpha_engine.data.sources  # noqa: F401  (triggers source registrations)


# Bar specs the bband_volume_setup strategy consumes. Daily for the state
# machine's setup detection; 1-minute for entry/exit triggers.
_REQUIRED_BAR_SPECS: tuple[str, ...] = ("1-DAY-LAST", "1-MINUTE-LAST")


def _cache_root() -> Path:
    """Project-wide cache root. Shared across all envs (per Phase 2 spec)."""
    # tools/alpha_engine/src/alpha_engine/engine/cache_loader.py
    #   .parents[0] = engine
    #   .parents[1] = alpha_engine
    #   .parents[2] = src
    #   .parents[3] = alpha_engine (tool root)
    return Path(__file__).resolve().parents[3] / "cache"


def _parse_dates(cfg: EnvConfig) -> tuple[datetime, datetime]:
    if not cfg.data.start_date or not cfg.data.end_date:
        raise ValueError(
            "cache_loader requires cfg.data.start_date and cfg.data.end_date "
            "(YYYY-MM-DD). The config loader should have already enforced this."
        )
    sd = datetime.strptime(cfg.data.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    ed = datetime.strptime(cfg.data.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return sd, ed


def _venue_for_source(source_id: str, fallback: str) -> str:
    """Return the cache-key venue string for a given source.

    Alpaca returns the same series regardless of US equity venue, so we
    bucket all Alpaca-sourced partitions under a single 'ALPACA' key. Other
    sources fall back to the instrument's declared Nautilus venue.
    """
    if source_id == "alpaca_historical":
        return "ALPACA"
    return fallback


def _bare_symbol_for_source(source_id: str, raw_symbol: str) -> str:
    """The symbol string to pass to the source's fetch().

    Alpaca's API only knows bare symbols (no venue suffix); IBKR's
    historical source already takes the full instrument_id. Adjust as we
    onboard more sources.
    """
    if source_id == "alpaca_historical":
        return raw_symbol
    # Default: send what the cache layer was keyed on.
    return raw_symbol


def _df_to_bars(df: pd.DataFrame, bar_type) -> list:
    """Convert a cache DataFrame (ts/open/high/low/close/volume) to Nautilus Bars."""
    from nautilus_trader.model.data import Bar
    from nautilus_trader.model.objects import Price, Quantity

    bars: list = []
    for row in df.itertuples(index=False):
        ts = int(row.ts)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{float(row.open):.2f}"),
                high=Price.from_str(f"{float(row.high):.2f}"),
                low=Price.from_str(f"{float(row.low):.2f}"),
                close=Price.from_str(f"{float(row.close):.2f}"),
                volume=Quantity.from_int(int(row.volume)),
                ts_event=ts,
                ts_init=ts,
            )
        )
    return bars


def build_engine_from_cache(
    cfg: EnvConfig, paths: EnvPaths
) -> Tuple["object", list]:
    """Build a BacktestEngine populated with cached historical bars.

    Returns (engine, [InstrumentId, ...]). The engine has one Venue (parsed
    from the first instrument), one Equity per instrument, and a combined
    list of Bars across all (instrument, bar_spec) pairs.
    """
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import BarSpecification, BarType
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

    start_dt, end_dt = _parse_dates(cfg)
    cache = HistoricalDataCache(root=_cache_root(), registry=default_registry)

    # Map "DAY"/"MINUTE" → BarSpecification once.
    daily_spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    minute_spec = BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST)
    spec_by_str = {
        "1-DAY-LAST": daily_spec,
        "1-MINUTE-LAST": minute_spec,
    }

    instrument_ids: list = []
    instruments_to_add: list = []
    venues_added: set[str] = set()
    all_bars: list = []
    venue_obj_for_first: Venue | None = None

    # Engine setup deferred until we know the venue.
    engine_config = BacktestEngineConfig(trader_id="ALPHA-001-BT")
    engine = BacktestEngine(config=engine_config)

    for iid_str in cfg.data.instruments:
        instrument_id = InstrumentId.from_str(iid_str)
        venue = instrument_id.venue
        if venue_obj_for_first is None:
            venue_obj_for_first = venue
        bare_symbol = instrument_id.symbol.value

        # Add venue + equity once per unique venue.
        venue_key = str(venue)
        if venue_key not in venues_added:
            engine.add_venue(
                venue=venue,
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency=USD,
                starting_balances=[Money(1_000_000, USD)],
            )
            venues_added.add(venue_key)

        equity = Equity(
            instrument_id=instrument_id,
            raw_symbol=Symbol(bare_symbol),
            currency=USD,
            price_precision=2,
            price_increment=Price.from_str("0.01"),
            lot_size=Quantity.from_int(1),
            ts_event=0,
            ts_init=0,
        )
        engine.add_instrument(equity)
        instruments_to_add.append(equity)
        instrument_ids.append(instrument_id)

        cache_venue = _venue_for_source(cfg.data.historical_source, str(venue))
        cache_symbol = _bare_symbol_for_source(cfg.data.historical_source, bare_symbol)

        for bar_spec_str in _REQUIRED_BAR_SPECS:
            df = cache.fetch(
                venue=cache_venue,
                instrument_id=cache_symbol,
                bar_spec=bar_spec_str,
                start=start_dt,
                end=end_dt,
                source_id=cfg.data.historical_source,
            )
            if df.empty:
                continue
            bar_type = BarType(
                instrument_id=instrument_id,
                bar_spec=spec_by_str[bar_spec_str],
                aggregation_source=AggregationSource.EXTERNAL,
            )
            all_bars.extend(_df_to_bars(df, bar_type))

    # Nautilus expects bars sorted by ts_event when mixing multiple bar types.
    all_bars.sort(key=lambda b: b.ts_event)
    if all_bars:
        engine.add_data(all_bars)

    return engine, instrument_ids
