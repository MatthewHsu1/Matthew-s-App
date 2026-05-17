from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alpha_engine.contracts.mode import Mode


@dataclass(frozen=True)
class StrategyConfig:
    ref: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VenueConfig:
    id: str
    account_kind: str  # "paper" | "live" — validated by loader, not here
    gateway_host: str = "host-gateway"
    gateway_port_paper: int = 4002
    gateway_port_live: int = 4001
    account_id_env: str = "IBKR_ACCOUNT_ID"
    username_env: str = "IBKR_USERNAME"
    password_env: str = "IBKR_PASSWORD"


@dataclass(frozen=True)
class DataConfig:
    live_source: str
    historical_source: str
    instruments: tuple[str, ...]
    bar_spec: str = "1-DAY-LAST"
    lookback_days: int = 365
    # ISO YYYY-MM-DD; required when mode=backtest with a non-synthetic source.
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class RiskConfig:
    max_position_usd: float | None = None
    max_daily_loss_usd: float | None = None
    price_band_bps: int | None = None
    market_hours_only: bool = False


@dataclass(frozen=True)
class ReportingConfig:
    benchmark: str | None = None
    timezone: str = "UTC"


@dataclass(frozen=True)
class EnvConfig:
    env_name: str
    mode: Mode
    strategy: StrategyConfig
    venue: VenueConfig
    data: DataConfig
    risk: RiskConfig
    reporting: ReportingConfig
