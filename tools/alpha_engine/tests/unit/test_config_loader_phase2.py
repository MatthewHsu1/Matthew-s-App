from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_engine.config.loader import ConfigError, load_env_config
from alpha_engine.contracts.mode import Mode


def _base_config():
    return {
        "env_name": "test_env",
        "mode": "paper",
        "strategy": {"ref": "toy_buy_and_hold", "params": {}},
        "venue": {
            "id": "ibkr",
            "account_kind": "paper",
            "gateway_host": "host-gateway",
            "gateway_port_paper": 4002,
            "gateway_port_live": 4001,
            "account_id_env": "IBKR_ACCOUNT_ID",
            "username_env": "IBKR_USERNAME",
            "password_env": "IBKR_PASSWORD",
        },
        "data": {
            "live_source": "ibkr",
            "historical_source": "ibkr_historical",
            "instruments": ["AAPL.NASDAQ"],
            "bar_spec": "1-DAY-LAST",
            "lookback_days": 365,
        },
        "risk": {
            "max_position_usd": 10000.0,
            "max_daily_loss_usd": 500.0,
        },
        "reporting": {"timezone": "UTC"},
    }


def test_loads_full_ibkr_paper_config(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_base_config()))
    cfg = load_env_config(cfg_path)
    assert cfg.mode is Mode.PAPER
    assert cfg.venue.id == "ibkr"
    assert cfg.venue.gateway_host == "host-gateway"
    assert cfg.venue.gateway_port_paper == 4002
    assert cfg.venue.account_id_env == "IBKR_ACCOUNT_ID"
    assert cfg.data.bar_spec == "1-DAY-LAST"
    assert cfg.data.lookback_days == 365


def test_mode_paper_requires_paper_account_kind(tmp_path: Path):
    raw = _base_config()
    raw["venue"]["account_kind"] = "live"
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(raw))
    with pytest.raises(ConfigError, match="paper"):
        load_env_config(cfg_path)


def test_bar_spec_required_when_historical_source_set(tmp_path: Path):
    raw = _base_config()
    del raw["data"]["bar_spec"]
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(raw))
    with pytest.raises(ConfigError):
        load_env_config(cfg_path)
