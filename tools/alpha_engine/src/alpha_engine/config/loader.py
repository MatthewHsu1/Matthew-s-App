from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode


class ConfigError(ValueError):
    """Raised when an env config fails schema or cross-field validation."""


def _load_schema() -> dict[str, Any]:
    schema_text = (
        resources.files("alpha_engine.config.schema")
        .joinpath("env.schema.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(schema_text)


def load_env_config(path: str | Path) -> EnvConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    try:
        jsonschema.validate(instance=raw, schema=_load_schema())
    except jsonschema.ValidationError as exc:
        raise ConfigError(f"schema validation failed: {exc.message}") from exc

    mode = Mode(raw["mode"])
    account_kind = raw["venue"]["account_kind"]
    historical = raw["data"]["historical_source"]
    risk_raw = raw.get("risk", {})

    # Cross-field rules.
    if mode is Mode.LIVE and account_kind == "paper":
        raise ConfigError(
            "mode=live conflicts with venue.account_kind=paper. "
            "Pick one — either mode=paper or venue.account_kind=live."
        )
    if mode is Mode.PAPER and account_kind != "paper":
        raise ConfigError(
            "mode=paper requires venue.account_kind=paper "
            f"(got account_kind={account_kind!r})."
        )
    if mode is Mode.BACKTEST and not historical:
        raise ConfigError("mode=backtest requires data.historical_source to be non-empty.")
    if mode is Mode.LIVE and risk_raw.get("max_daily_loss_usd") is None:
        raise ConfigError(
            "mode=live requires risk.max_daily_loss_usd to be set explicitly. "
            "Opt-in safety is unsafety."
        )

    return EnvConfig(
        env_name=raw["env_name"],
        mode=mode,
        strategy=StrategyConfig(
            ref=raw["strategy"]["ref"],
            params=dict(raw["strategy"].get("params", {})),
        ),
        venue=VenueConfig(
            id=raw["venue"]["id"],
            account_kind=account_kind,
            gateway_host=raw["venue"].get("gateway_host", "host-gateway"),
            gateway_port_paper=raw["venue"].get("gateway_port_paper", 4002),
            gateway_port_live=raw["venue"].get("gateway_port_live", 4001),
            account_id_env=raw["venue"].get("account_id_env", "IBKR_ACCOUNT_ID"),
            username_env=raw["venue"].get("username_env", "IBKR_USERNAME"),
            password_env=raw["venue"].get("password_env", "IBKR_PASSWORD"),
        ),
        data=DataConfig(
            live_source=raw["data"]["live_source"],
            historical_source=historical,
            instruments=tuple(raw["data"]["instruments"]),
            bar_spec=raw["data"].get("bar_spec", "1-DAY-LAST"),
            lookback_days=raw["data"].get("lookback_days", 365),
        ),
        risk=RiskConfig(
            max_position_usd=risk_raw.get("max_position_usd"),
            max_daily_loss_usd=risk_raw.get("max_daily_loss_usd"),
            price_band_bps=risk_raw.get("price_band_bps"),
            market_hours_only=risk_raw.get("market_hours_only", False),
        ),
        reporting=ReportingConfig(
            benchmark=raw.get("reporting", {}).get("benchmark"),
            timezone=raw.get("reporting", {}).get("timezone", "UTC"),
        ),
    )
