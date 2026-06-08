"""floor_v1 -- Python configs for Floor Trading backtest runs.

Backtest is the only supported mode in Plan 2. Paper/live wiring lands in
Plan 3 once the IBKR adapter is configured for TradeTick subscription
management and MOC-on-close submission.

Conventions
-----------
- Universe read from envs/floor_v1/universe.txt (one InstrumentId per line).
- Strategy/risk constants are module-level so tunings show in `git diff`.
- Output directory (outputs/) is created on demand; LoggingConfig writes
  log files there.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableActorConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import Bar, TradeTick

ENV_DIR: Path = Path(__file__).resolve().parent
OUTPUTS_DIR: Path = ENV_DIR / "outputs"
LOGS_DIR: Path = OUTPUTS_DIR / "logs"
SUMMARY_PATH: Path = OUTPUTS_DIR / "summary.json"
TRADES_PARQUET_PATH: Path = OUTPUTS_DIR / "trades.parquet"


def load_universe() -> list[str]:
    text = (ENV_DIR / "universe.txt").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


UNIVERSE: list[str] = load_universe()

# Strategy tunables.
BBAND_PERIOD: int = 20
BBAND_STDDEV: float = 2.0
VOLUME_AVG_PERIOD: int = 20
DAY1_VOLUME_MULTIPLIER: float = 2.0
BURST_WINDOW_SECONDS: float = 5.0
BASELINE_WINDOW_SECONDS: float = 120.0
SPIKE_VOLUME_MULTIPLIER: float = 10.0
STOP_PCT_BELOW_T1: float = 1.5
TRANCHE_COUNT: int = 2
MAX_HOLD_DAYS: int = 3

# Sizing.
TRANCHE_DOLLARS: float = 5_000.0
MIN_PRICE_USD: float = 5.0
PRICE_BAND_PCT: float = 5.0
MAX_CONCURRENT_POSITIONS: int = 5

# Catalog (overridden by the runner if --catalog-path is passed).
CATALOG_PATH: str = "/mnt/HDD/Projects/Financial_App/catalog"

# Backtest window -- narrow default; runners can override.
BACKTEST_START: str = "2026-01-05"
BACKTEST_END: str = "2026-01-15"

TRADER_ID_BACKTEST: str = "FLOOR-V1-BACKTEST"


def _strategy_config_dict() -> dict:
    return {
        "instrument_ids": UNIVERSE,
        "tranche_dollars": TRANCHE_DOLLARS,
        "min_price_usd": MIN_PRICE_USD,
        "price_band_pct": PRICE_BAND_PCT,
        "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
        "bband_period": BBAND_PERIOD,
        "bband_stddev": BBAND_STDDEV,
        "volume_avg_period": VOLUME_AVG_PERIOD,
        "day1_volume_multiplier": DAY1_VOLUME_MULTIPLIER,
        "burst_window_seconds": BURST_WINDOW_SECONDS,
        "baseline_window_seconds": BASELINE_WINDOW_SECONDS,
        "spike_volume_multiplier": SPIKE_VOLUME_MULTIPLIER,
        "stop_pct_below_t1": STOP_PCT_BELOW_T1,
        "tranche_count": TRANCHE_COUNT,
        "max_hold_days": MAX_HOLD_DAYS,
    }


def _scan_actor_config_dict() -> dict:
    return {
        "instrument_ids": UNIVERSE,
        "bband_period": BBAND_PERIOD,
        "bband_stddev": BBAND_STDDEV,
        "volume_avg_period": VOLUME_AVG_PERIOD,
        "day1_volume_multiplier": DAY1_VOLUME_MULTIPLIER,
    }


def importable_strategy() -> ImportableStrategyConfig:
    return ImportableStrategyConfig(
        strategy_path="alpha_engine.strategies.floor_trading.strategy:FloorTradingStrategy",
        config_path="alpha_engine.strategies.floor_trading.strategy:FloorTradingNautilusParams",
        config=_strategy_config_dict(),
    )


def importable_scan_actor() -> ImportableActorConfig:
    return ImportableActorConfig(
        actor_path="alpha_engine.strategies.floor_trading.scan_actor:FloorScanActor",
        config_path="alpha_engine.strategies.floor_trading.scan_actor:FloorScanActorConfig",
        config=_scan_actor_config_dict(),
    )


def _venue_names_in_universe() -> set[str]:
    return {iid.split(".")[-1] for iid in UNIVERSE}


def backtest_venues() -> list[BacktestVenueConfig]:
    return [
        BacktestVenueConfig(
            name=venue, oms_type="NETTING", account_type="MARGIN",
            base_currency="USD", starting_balances=["1_000_000 USD"],
        )
        for venue in sorted(_venue_names_in_universe())
    ]


def backtest_data_configs(*, start: str, end: str, catalog_path: str) -> list[BacktestDataConfig]:
    configs: list[BacktestDataConfig] = []
    for iid in UNIVERSE:
        # Daily bars for the scan actor + state-machine session_close.
        configs.append(BacktestDataConfig(
            catalog_path=catalog_path,
            data_cls=Bar.fully_qualified_name(),
            bar_types=[f"{iid}-1-DAY-LAST-EXTERNAL"],
            start_time=start, end_time=end,
        ))
        # TradeTicks for the strategy's intraday logic.
        configs.append(BacktestDataConfig(
            catalog_path=catalog_path,
            data_cls=TradeTick.fully_qualified_name(),
            instrument_ids=[iid],
            start_time=start, end_time=end,
        ))
    return configs


def backtest_engine_config(*, logs_dir: Path = LOGS_DIR, trader_id: str = TRADER_ID_BACKTEST) -> BacktestEngineConfig:
    return BacktestEngineConfig(
        trader_id=trader_id,
        logging=LoggingConfig(log_directory=str(logs_dir), log_file_format="json"),
        actors=[importable_scan_actor()],
        strategies=[importable_strategy()],
    )


def backtest_run_config(
    *,
    start: str = BACKTEST_START,
    end: str = BACKTEST_END,
    catalog_path: str = CATALOG_PATH,
    logs_dir: Path = LOGS_DIR,
    trader_id: str = TRADER_ID_BACKTEST,
) -> BacktestRunConfig:
    return BacktestRunConfig(
        engine=backtest_engine_config(logs_dir=logs_dir, trader_id=trader_id),
        venues=backtest_venues(),
        data=backtest_data_configs(start=start, end=end, catalog_path=catalog_path),
        start=start, end=end,
    )


def run_started_now() -> datetime:
    return datetime.now(tz=timezone.utc)
