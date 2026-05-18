"""Tests catalog_loader.build_engine_from_catalog."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.engine.catalog_loader import (
    CatalogLoaderError,
    build_engine_from_catalog,
)
from tests.fixtures.tmp_catalog import build_tmp_catalog


def _make_cfg(*, catalog_path: str) -> EnvConfig:
    return EnvConfig(
        env_name="test_env",
        mode=Mode.BACKTEST,
        strategy=StrategyConfig(ref="bband_volume_setup", params={}),
        venue=VenueConfig(id="nasdaq_sim", account_kind="paper"),
        data=DataConfig(
            live_source="venue",
            historical_source="parquet_catalog",
            instruments=("MSFT.NASDAQ",),
            bar_spec="1-DAY-LAST",
            start_date="2024-01-02",
            end_date="2024-01-10",
            catalog_path=catalog_path,
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(timezone="UTC"),
    )


def test_build_engine_loads_daily_and_minute_bars(tmp_path: Path) -> None:
    catalog_root = tmp_path / "catalog"
    build_tmp_catalog(
        root=catalog_root, symbol="MSFT", venue="NASDAQ",
        bar_spec="1-DAY-LAST", n_bars=10,
        start=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    build_tmp_catalog(
        root=catalog_root, symbol="MSFT", venue="NASDAQ",
        bar_spec="1-MINUTE-LAST", n_bars=10,
        start=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
    )

    cfg = _make_cfg(catalog_path=str(catalog_root))
    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="test_env")
    paths.ensure_dirs()

    engine, instrument_ids = build_engine_from_catalog(cfg, paths)

    assert len(instrument_ids) == 1
    assert str(instrument_ids[0]) == "MSFT.NASDAQ"
    assert engine is not None


def test_build_engine_raises_when_instrument_missing(tmp_path: Path) -> None:
    """Configured instrument that's not present in the catalog must error loudly."""
    catalog_root = tmp_path / "empty_catalog"
    catalog_root.mkdir()

    cfg = _make_cfg(catalog_path=str(catalog_root))
    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="test_env")
    paths.ensure_dirs()

    with pytest.raises(CatalogLoaderError, match="not present in catalog"):
        build_engine_from_catalog(cfg, paths)


def test_build_engine_raises_when_no_bars(tmp_path: Path) -> None:
    """Catalog has the instrument but no bars in range → 'no bars found' error."""
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import Price, Quantity
    from nautilus_trader.persistence.catalog import ParquetDataCatalog

    catalog_root = tmp_path / "catalog_no_bars"
    catalog_root.mkdir()
    catalog = ParquetDataCatalog(path=str(catalog_root))
    instrument = Equity(
        instrument_id=InstrumentId(Symbol("MSFT"), Venue("NASDAQ")),
        raw_symbol=Symbol("MSFT"),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )
    catalog.write_data([instrument])

    cfg = _make_cfg(catalog_path=str(catalog_root))
    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="test_env")
    paths.ensure_dirs()

    with pytest.raises(CatalogLoaderError, match="no bars found"):
        build_engine_from_catalog(cfg, paths)
