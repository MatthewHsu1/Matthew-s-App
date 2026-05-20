"""bband_v1 — Python configs for backtest + paper + live runs.

Replaces the deleted config.json. Imported by run_backtest.py, run_paper.py
and run_live.py; each runner pulls only the factories it needs.

Conventions
-----------
- The universe is read from envs/bband_v1/universe.txt (one InstrumentId per
  line, '#' comments ignored).
- Strategy parameters and risk thresholds are module-level constants so they
  appear in `git diff` when tuned.
- Output directory (`outputs/`) is created on demand by the runner scripts;
  the Nautilus LoggingConfig writes log files there.
- IBKR account_id is read from the IBKR_ACCOUNT_ID env var (loaded from
  outputs/secrets.env by config.secrets.load_secrets_file).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersExecClientConfig,
    InteractiveBrokersInstrumentProviderConfig,
)
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableActorConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.model.data import Bar


ENV_DIR: Path = Path(__file__).resolve().parent
OUTPUTS_DIR: Path = ENV_DIR / "outputs"
LOGS_DIR: Path = OUTPUTS_DIR / "logs"
SUMMARY_PATH: Path = OUTPUTS_DIR / "summary.json"
TRADES_PARQUET_PATH: Path = OUTPUTS_DIR / "trades.parquet"
KILL_SWITCH_PATH: Path = OUTPUTS_DIR / "kill.flag"
SECRETS_PATH: Path = OUTPUTS_DIR / "secrets.env"


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_universe() -> list[str]:
    """Read envs/bband_v1/universe.txt — comments + blank lines ignored."""
    text = (ENV_DIR / "universe.txt").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


UNIVERSE: list[str] = load_universe()


# ---------------------------------------------------------------------------
# Strategy + actor tunables
# ---------------------------------------------------------------------------

BBAND_PERIOD: int = 20
BBAND_STDDEV: float = 2.0
VOLUME_AVG_PERIOD: int = 20
DAY1_VOLUME_MULTIPLIER: float = 2.0
SPIKE_VOLUME_MULTIPLIER: float = 3.0
SPIKE_PRICE_MOVE_PCT: float = 1.5
SURGE_VOLUME_MULTIPLIER: float = 2.0
SURGE_REQUIRES_PRICE_BELOW_OPEN: bool = True
SURGE_MIN_GAP_MINUTES: int = 30
TRANCHE_COUNT: int = 3
HARD_STOP_PCT_BELOW_DAY1_LOW: float = 2.0
MAX_HOLD_DAYS: int = 5

# Strategy-only (sizing + inline guards)
TRANCHE_DOLLARS: float = 3000.0
MIN_PRICE_USD: float = 10.0
PRICE_BAND_PCT: float = 5.0
MINUTE_BAR_STEP: int = 5

# Risk monitor
MAX_DAILY_LOSS_USD: float = 50_000.0
SESSION_OPEN_UTC: str = "13:30"   # 09:30 ET in DST
SESSION_CLOSE_UTC: str = "20:00"  # 16:00 ET in DST

# Catalog (PR 1)
CATALOG_PATH: str = "/mnt/HDD/Projects/Financial_App/catalog"

# Backtest window — narrow because the catalog only has 2024 data populated.
BACKTEST_START: str = "2024-01-01"
BACKTEST_END: str = "2024-12-31"

# Identity
TRADER_ID_BACKTEST: str = "BBAND-V1-BACKTEST"
TRADER_ID_PAPER: str = "BBAND-V1-PAPER"
TRADER_ID_LIVE: str = "BBAND-V1-LIVE"


# ---------------------------------------------------------------------------
# Importable strategy + actor configs (used by both backtest + live)
# ---------------------------------------------------------------------------

def _strategy_config_dict() -> dict:
    return {
        "instrument_ids": UNIVERSE,
        "tranche_dollars": TRANCHE_DOLLARS,
        "min_price_usd": MIN_PRICE_USD,
        "price_band_pct": PRICE_BAND_PCT,
        "minute_bar_step": MINUTE_BAR_STEP,
        "bband_period": BBAND_PERIOD,
        "bband_stddev": BBAND_STDDEV,
        "volume_avg_period": VOLUME_AVG_PERIOD,
        "day1_volume_multiplier": DAY1_VOLUME_MULTIPLIER,
        "spike_volume_multiplier": SPIKE_VOLUME_MULTIPLIER,
        "spike_price_move_pct": SPIKE_PRICE_MOVE_PCT,
        "surge_volume_multiplier": SURGE_VOLUME_MULTIPLIER,
        "surge_requires_price_below_open": SURGE_REQUIRES_PRICE_BELOW_OPEN,
        "surge_min_gap_minutes": SURGE_MIN_GAP_MINUTES,
        "tranche_count": TRANCHE_COUNT,
        "hard_stop_pct_below_day1_low": HARD_STOP_PCT_BELOW_DAY1_LOW,
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


def _risk_monitor_config_dict() -> dict:
    return {
        "max_daily_loss_usd": MAX_DAILY_LOSS_USD,
        "session_open_et": SESSION_OPEN_UTC,
        "session_close_et": SESSION_CLOSE_UTC,
        "kill_switch_path": str(KILL_SWITCH_PATH),
    }


def importable_strategy() -> ImportableStrategyConfig:
    return ImportableStrategyConfig(
        strategy_path="alpha_engine.strategies.bband_volume_setup.strategy:BBandVolumeSetupStrategy",
        config_path="alpha_engine.strategies.bband_volume_setup.strategy:BBandVolumeSetupNautilusParams",
        config=_strategy_config_dict(),
    )


def importable_scan_actor() -> ImportableActorConfig:
    return ImportableActorConfig(
        actor_path="alpha_engine.scan.bband_scan_actor:BBandScanActor",
        config_path="alpha_engine.scan.bband_scan_actor:BBandScanActorConfig",
        config=_scan_actor_config_dict(),
    )


def importable_risk_monitor() -> ImportableActorConfig:
    return ImportableActorConfig(
        actor_path="alpha_engine.risk.risk_monitor_actor:RiskMonitorActor",
        config_path="alpha_engine.risk.risk_monitor_actor:RiskMonitorActorConfig",
        config=_risk_monitor_config_dict(),
    )


# ---------------------------------------------------------------------------
# Backtest config
# ---------------------------------------------------------------------------

def _venue_names_in_universe() -> set[str]:
    return {iid.split(".")[-1] for iid in UNIVERSE}


def backtest_venues() -> list[BacktestVenueConfig]:
    return [
        BacktestVenueConfig(
            name=venue,
            oms_type="NETTING",
            account_type="MARGIN",
            base_currency="USD",
            starting_balances=["1_000_000 USD"],
        )
        for venue in sorted(_venue_names_in_universe())
    ]


def backtest_data_configs(*, start: str, end: str, catalog_path: str) -> list[BacktestDataConfig]:
    """One BacktestDataConfig per (instrument, bar spec) combination.

    The strategy consumes 1-DAY-LAST + 5-MINUTE-LAST. Each config tells
    BacktestNode which catalog file to stream into the engine.
    """
    configs: list[BacktestDataConfig] = []
    for iid in UNIVERSE:
        for bar_spec in ("1-DAY-LAST", "5-MINUTE-LAST"):
            configs.append(
                BacktestDataConfig(
                    catalog_path=catalog_path,
                    data_cls=Bar.fully_qualified_name(),
                    bar_types=[f"{iid}-{bar_spec}-EXTERNAL"],
                    start_time=start,
                    end_time=end,
                )
            )
    return configs


def backtest_engine_config(
    *,
    logs_dir: Path = LOGS_DIR,
    trader_id: str = TRADER_ID_BACKTEST,
) -> BacktestEngineConfig:
    return BacktestEngineConfig(
        trader_id=trader_id,
        logging=LoggingConfig(
            log_directory=str(logs_dir),
            log_file_format="json",
        ),
        actors=[importable_scan_actor(), importable_risk_monitor()],
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
        start=start,
        end=end,
    )


# ---------------------------------------------------------------------------
# Paper / live config (TradingNode)
# ---------------------------------------------------------------------------

def _ibkr_data_client_config() -> InteractiveBrokersDataClientConfig:
    return InteractiveBrokersDataClientConfig(
        ibg_host="host-gateway",
        ibg_port=4002,  # paper port; overridden to 4001 for live
        ibg_client_id=1,
        instrument_provider=InteractiveBrokersInstrumentProviderConfig(),
    )


def _ibkr_exec_client_config(*, account_id: str, port: int) -> InteractiveBrokersExecClientConfig:
    return InteractiveBrokersExecClientConfig(
        ibg_host="host-gateway",
        ibg_port=port,
        ibg_client_id=1,
        account_id=account_id,
        instrument_provider=InteractiveBrokersInstrumentProviderConfig(),
    )


def trading_node_config(
    *,
    is_live: bool,
    logs_dir: Path = LOGS_DIR,
) -> TradingNodeConfig:
    account_id = os.environ["IBKR_ACCOUNT_ID"]
    port = 4001 if is_live else 4002
    trader_id = TRADER_ID_LIVE if is_live else TRADER_ID_PAPER

    return TradingNodeConfig(
        trader_id=trader_id,
        logging=LoggingConfig(
            log_directory=str(logs_dir),
            log_file_format="json",
        ),
        actors=[importable_scan_actor(), importable_risk_monitor()],
        strategies=[importable_strategy()],
        data_clients={
            "IB": InteractiveBrokersDataClientConfig(
                ibg_host="host-gateway",
                ibg_port=port,
                ibg_client_id=1,
                instrument_provider=InteractiveBrokersInstrumentProviderConfig(),
            ),
        },
        exec_clients={
            "IB": _ibkr_exec_client_config(account_id=account_id, port=port),
        },
    )


def run_started_now() -> datetime:
    return datetime.now(tz=timezone.utc)
