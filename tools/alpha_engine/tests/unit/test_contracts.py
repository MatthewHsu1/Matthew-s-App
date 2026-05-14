from __future__ import annotations

import pytest

from alpha_engine.contracts.mode import Mode


def test_mode_values():
    assert Mode("backtest") is Mode.BACKTEST
    assert Mode("paper") is Mode.PAPER
    assert Mode("live") is Mode.LIVE


def test_mode_rejects_unknown():
    with pytest.raises(ValueError):
        Mode("simulator")


def test_mode_is_serializable_back_to_string():
    assert Mode.BACKTEST.value == "backtest"


def test_env_config_is_frozen_and_has_expected_fields():
    from alpha_engine.contracts.config import (
        EnvConfig,
        StrategyConfig,
        VenueConfig,
        DataConfig,
        RiskConfig,
        ReportingConfig,
    )
    import dataclasses

    cfg = EnvConfig(
        env_name="toy",
        mode=Mode.BACKTEST,
        strategy=StrategyConfig(ref="toy_buy_and_hold", params={"qty": 10}),
        venue=VenueConfig(id="ibkr", account_kind="paper"),
        data=DataConfig(
            live_source="venue",
            historical_source="fixture_catalog",
            instruments=("MSFT.NASDAQ",),
        ),
        risk=RiskConfig(
            max_position_usd=25000.0,
            max_daily_loss_usd=500.0,
            price_band_bps=50,
            market_hours_only=True,
        ),
        reporting=ReportingConfig(benchmark="SPY", timezone="America/New_York"),
    )
    assert cfg.env_name == "toy"
    assert cfg.mode is Mode.BACKTEST
    assert cfg.strategy.ref == "toy_buy_and_hold"
    assert cfg.data.instruments == ("MSFT.NASDAQ",)

    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.env_name = "other"  # type: ignore[misc]
