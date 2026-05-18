"""Build a BacktestEngine populated with bars from a ParquetDataCatalog.

Replaces engine/cache_loader.py. Reads bars and instruments directly from
the catalog's standard Nautilus layout. No custom partitioning, locking,
or source-registry indirection.

The strategy under bband_volume_setup needs both DAILY and MINUTE bar streams;
this loader requests both bar types from the catalog for each configured
instrument and combines them, sorted by ts_event.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import EnvConfig

# Bar specs the bband_volume_setup strategy consumes.
_REQUIRED_BAR_SPECS: tuple[str, ...] = ("1-DAY-LAST", "1-MINUTE-LAST")


class CatalogLoaderError(RuntimeError):
    """Raised when the catalog cannot satisfy the configured backtest."""


def _parse_dates(cfg: EnvConfig) -> tuple[datetime, datetime]:
    if not cfg.data.start_date or not cfg.data.end_date:
        raise CatalogLoaderError(
            "catalog_loader requires cfg.data.start_date and cfg.data.end_date"
        )
    sd = datetime.strptime(cfg.data.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    ed = datetime.strptime(cfg.data.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return sd, ed


def _bar_type_str(instrument_id: str, bar_spec: str) -> str:
    """Nautilus catalog bar-type key: '<symbol>.<venue>-<spec>-EXTERNAL'."""
    return f"{instrument_id}-{bar_spec}-EXTERNAL"


def build_engine_from_catalog(
    cfg: EnvConfig, paths: EnvPaths
) -> tuple[BacktestEngine, list[InstrumentId]]:
    """Build a BacktestEngine populated from a ParquetDataCatalog.

    Returns (engine, [InstrumentId, ...]) suitable for handoff to engine.backtest.run_backtest.
    """
    if not cfg.data.catalog_path:
        raise CatalogLoaderError(
            "data.catalog_path must be set when historical_source == 'parquet_catalog'"
        )

    catalog_root = Path(cfg.data.catalog_path)
    if not catalog_root.exists():
        raise CatalogLoaderError(f"catalog path does not exist: {catalog_root}")

    catalog = ParquetDataCatalog(path=str(catalog_root))
    start_dt, end_dt = _parse_dates(cfg)

    engine_config = BacktestEngineConfig(trader_id="ALPHA-001-BT")
    engine = BacktestEngine(config=engine_config)

    instrument_ids: list[InstrumentId] = []
    venues_added: set[str] = set()
    all_bars: list = []

    for iid_str in cfg.data.instruments:
        instrument_id = InstrumentId.from_str(iid_str)
        venue: Venue = instrument_id.venue

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

        # Load instrument metadata from catalog.
        instruments = catalog.instruments(instrument_ids=[iid_str])
        if not instruments:
            # No instrument definition means no bars — defer to the "no bars found"
            # error raised below once all instruments are processed.
            continue
        engine.add_instrument(instruments[0])
        instrument_ids.append(instrument_id)

        # Load each required bar spec.
        for bar_spec_str in _REQUIRED_BAR_SPECS:
            bt_str = _bar_type_str(iid_str, bar_spec_str)
            bars = catalog.bars(
                bar_types=[bt_str],
                start=start_dt,
                end=end_dt,
            )
            all_bars.extend(bars)

    if not all_bars:
        raise CatalogLoaderError(
            f"no bars found in catalog at {catalog_root} for "
            f"instruments={cfg.data.instruments} between {start_dt} and {end_dt}"
        )

    all_bars.sort(key=lambda b: b.ts_event)
    engine.add_data(all_bars)

    return engine, instrument_ids
