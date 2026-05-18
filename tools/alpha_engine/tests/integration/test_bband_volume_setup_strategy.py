"""Integration test: BBand+Volume strategy boots and runs to completion.

Builds a tmp ParquetDataCatalog with daily + minute bars for one symbol,
then runs the strategy via build_engine_from_catalog. The strategy subscribes
to both bar streams; the catalog provides both. Linear price walk doesn't
trigger any Day-1 BBand setup, so the state machine stays IDLE and zero
orders are submitted. This test pins the catalog + strategy plumbing only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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
from alpha_engine.engine.catalog_loader import build_engine_from_catalog
from alpha_engine.strategies.bband_volume_setup.strategy import (
    BBandVolumeSetupNautilusParams,
    BBandVolumeSetupStrategy,
)
from tests.fixtures.tmp_catalog import build_tmp_catalog


def test_strategy_boots_with_catalog_data_no_crash(tmp_path: Path) -> None:
    catalog_root = tmp_path / "catalog"
    build_tmp_catalog(
        root=catalog_root, symbol="MSFT", venue="NASDAQ",
        bar_spec="1-DAY-LAST", n_bars=30,
        start=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )
    build_tmp_catalog(
        root=catalog_root, symbol="MSFT", venue="NASDAQ",
        bar_spec="5-MINUTE-LAST", n_bars=30,
        start=datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc),
    )

    cfg = _make_cfg(catalog_path=str(catalog_root))
    paths = EnvPaths(envs_root=tmp_path / "envs", env_name="test_env")
    paths.ensure_dirs()

    engine, instrument_ids = build_engine_from_catalog(cfg, paths)
    params = BBandVolumeSetupNautilusParams(
        instrument_ids=[str(instrument_ids[0])],
        minute_bar_step=5,
    )
    strategy = BBandVolumeSetupStrategy(config=params)
    engine.add_strategy(strategy)
    engine.run()
    # Strategy must reach the end of the bar stream without raising.
    # The linear price walk + constant volume produced by build_tmp_catalog
    # does not trigger a Day-1 BBand+Volume setup, so the state machine
    # stays IDLE and zero orders are submitted.


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
            start_date="2026-01-05",
            end_date="2026-01-15",
            catalog_path=catalog_path,
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(timezone="UTC"),
    )
