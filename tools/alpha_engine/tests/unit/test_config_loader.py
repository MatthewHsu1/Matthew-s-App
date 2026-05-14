from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_engine.config.loader import load_env_config, ConfigError
from alpha_engine.contracts.mode import Mode


@pytest.fixture
def valid_config_dict():
    return {
        "env_name": "toy",
        "mode": "backtest",
        "strategy": {"ref": "toy_buy_and_hold", "params": {"qty": 10}},
        "venue": {"id": "ibkr", "account_kind": "paper"},
        "data": {
            "live_source": "venue",
            "historical_source": "fixture_catalog",
            "instruments": ["MSFT.NASDAQ"],
        },
        "risk": {
            "max_position_usd": 25000,
            "max_daily_loss_usd": 500,
            "price_band_bps": 50,
            "market_hours_only": True,
        },
        "reporting": {"benchmark": "SPY", "timezone": "America/New_York"},
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_loads_valid_config(tmp_path, valid_config_dict):
    cfg = load_env_config(_write(tmp_path, valid_config_dict))
    assert cfg.env_name == "toy"
    assert cfg.mode is Mode.BACKTEST
    assert cfg.data.instruments == ("MSFT.NASDAQ",)


def test_rejects_unknown_field(tmp_path, valid_config_dict):
    valid_config_dict["extra"] = "nope"
    with pytest.raises(ConfigError):
        load_env_config(_write(tmp_path, valid_config_dict))


def test_rejects_live_with_paper_account_kind(tmp_path, valid_config_dict):
    valid_config_dict["mode"] = "live"
    valid_config_dict["venue"]["account_kind"] = "paper"
    with pytest.raises(ConfigError, match="account_kind"):
        load_env_config(_write(tmp_path, valid_config_dict))


def test_rejects_backtest_without_historical_source(tmp_path, valid_config_dict):
    valid_config_dict["data"]["historical_source"] = ""
    with pytest.raises(ConfigError):
        load_env_config(_write(tmp_path, valid_config_dict))


def test_rejects_live_without_max_daily_loss(tmp_path, valid_config_dict):
    valid_config_dict["mode"] = "live"
    valid_config_dict["venue"]["account_kind"] = "live"
    del valid_config_dict["risk"]["max_daily_loss_usd"]
    with pytest.raises(ConfigError, match="max_daily_loss_usd"):
        load_env_config(_write(tmp_path, valid_config_dict))


def test_accepts_paper_without_max_daily_loss(tmp_path, valid_config_dict):
    del valid_config_dict["risk"]["max_daily_loss_usd"]
    cfg = load_env_config(_write(tmp_path, valid_config_dict))
    assert cfg.risk.max_daily_loss_usd is None
