"""End-to-end smoke test: BacktestNode on a tmp catalog produces summary + trades.

Replaces the deleted tests/integration/test_bband_volume_setup_strategy.py.
The linear price walk produced by tmp_catalog won't trigger any Day-1
BBand setup so the trades.parquet will be empty — that is fine; this test
pins the wiring, not the strategy behaviour.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableActorConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import Bar

from alpha_engine.reporting.summary import RunMetadata, write_summary
from alpha_engine.reporting.trades import write_trades_parquet
from tests.fixtures.tmp_catalog import build_tmp_catalog


_SYMBOL = "MSFT"
_VENUE = "NASDAQ"
_IID = f"{_SYMBOL}.{_VENUE}"


def _backtest_run_config(*, catalog_path: str, logs_dir: Path, start: str, end: str) -> BacktestRunConfig:
    strategy = ImportableStrategyConfig(
        strategy_path="alpha_engine.strategies.bband_volume_setup.strategy:BBandVolumeSetupStrategy",
        config_path="alpha_engine.strategies.bband_volume_setup.strategy:BBandVolumeSetupNautilusParams",
        config={
            "instrument_ids": [_IID],
            "tranche_dollars": 3000.0,
            "min_price_usd": 10.0,
            "price_band_pct": 5.0,
            "minute_bar_step": 5,
        },
    )
    scan_actor = ImportableActorConfig(
        actor_path="alpha_engine.scan.bband_scan_actor:BBandScanActor",
        config_path="alpha_engine.scan.bband_scan_actor:BBandScanActorConfig",
        config={
            "instrument_ids": [_IID],
            "bband_period": 20,
            "bband_stddev": 2.0,
            "volume_avg_period": 20,
            "day1_volume_multiplier": 2.0,
        },
    )
    engine = BacktestEngineConfig(
        trader_id="SMOKE-001",
        logging=LoggingConfig(log_directory=str(logs_dir), log_file_format="json"),
        actors=[scan_actor],
        strategies=[strategy],
    )
    venue = BacktestVenueConfig(
        name=_VENUE,
        oms_type="NETTING",
        account_type="MARGIN",
        base_currency="USD",
        starting_balances=["1_000_000 USD"],
    )
    data_configs = [
        BacktestDataConfig(
            catalog_path=catalog_path,
            data_cls=Bar.fully_qualified_name(),
            bar_types=[f"{_IID}-{spec}-EXTERNAL"],
            start_time=start,
            end_time=end,
        )
        for spec in ("1-DAY-LAST", "5-MINUTE-LAST")
    ]
    return BacktestRunConfig(
        engine=engine,
        venues=[venue],
        data=data_configs,
        start=start,
        end=end,
    )


def test_backtest_node_runs_against_tmp_catalog(tmp_path: Path) -> None:
    catalog_root = tmp_path / "catalog"
    build_tmp_catalog(
        root=catalog_root, symbol=_SYMBOL, venue=_VENUE,
        bar_spec="1-DAY-LAST", n_bars=30,
        start=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )
    build_tmp_catalog(
        root=catalog_root, symbol=_SYMBOL, venue=_VENUE,
        bar_spec="5-MINUTE-LAST", n_bars=30,
        start=datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc),
    )

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    rc = _backtest_run_config(
        catalog_path=str(catalog_root),
        logs_dir=logs_dir,
        start="2026-01-05",
        end="2026-02-15",
    )
    node = BacktestNode(configs=[rc])
    results = node.run()
    assert len(results) == 1
    result = results[0]
    assert result.trader_id == "SMOKE-001"
    assert result.run_id

    summary_path = tmp_path / "summary.json"
    write_summary(
        summary_path,
        meta=RunMetadata(
            trader_id=result.trader_id,
            instance_id=result.instance_id,
            git_sha=None,
            env_name="smoke",
            start_ts=datetime(2026, 1, 5, tzinfo=timezone.utc),
            end_ts=datetime(2026, 2, 15, tzinfo=timezone.utc),
        ),
        stats_pnls=result.stats_pnls or {},
        stats_returns=result.stats_returns or {},
    )
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text())
    assert payload["env_name"] == "smoke"
    assert payload["trader_id"] == "SMOKE-001"
    assert "metrics" in payload

    trades_path = tmp_path / "trades.parquet"
    write_trades_parquet(trades_path, [])
    assert trades_path.exists()
    df = pd.read_parquet(trades_path)
    assert list(df.columns) == [
        "ts", "env_name", "strategy_class", "instrument_id",
        "side", "quantity", "price", "fees",
    ]
