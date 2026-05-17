"""Tests for start_date / end_date fields on the data config (Phase 2.1).

Cross-field rule: when mode == backtest and historical_source != synthetic_fixture,
both start_date and end_date are required and must parse as ISO YYYY-MM-DD.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_engine.config.loader import ConfigError, load_env_config


def _base_backtest_config() -> dict:
    return {
        "env_name": "backtest_alpaca",
        "mode": "backtest",
        "strategy": {"ref": "bband_volume_setup", "params": {}},
        "venue": {"id": "nasdaq_sim", "account_kind": "paper"},
        "data": {
            "live_source": "venue",
            "historical_source": "alpaca_historical",
            "instruments": ["MSFT.NASDAQ"],
            "bar_spec": "1-DAY-LAST",
            "start_date": "2025-01-01",
            "end_date": "2025-02-01",
        },
        "risk": {},
        "reporting": {"timezone": "UTC"},
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_loads_backtest_alpaca_with_date_fields(tmp_path: Path) -> None:
    cfg = load_env_config(_write(tmp_path, _base_backtest_config()))
    assert cfg.data.start_date == "2025-01-01"
    assert cfg.data.end_date == "2025-02-01"
    assert cfg.data.historical_source == "alpaca_historical"


def test_synthetic_backtest_does_not_require_dates(tmp_path: Path) -> None:
    raw = _base_backtest_config()
    raw["data"]["historical_source"] = "synthetic_fixture"
    del raw["data"]["start_date"]
    del raw["data"]["end_date"]
    cfg = load_env_config(_write(tmp_path, raw))
    assert cfg.data.start_date is None
    assert cfg.data.end_date is None


def test_non_synthetic_backtest_requires_start_date(tmp_path: Path) -> None:
    raw = _base_backtest_config()
    del raw["data"]["start_date"]
    with pytest.raises(ConfigError, match="start_date"):
        load_env_config(_write(tmp_path, raw))


def test_non_synthetic_backtest_requires_end_date(tmp_path: Path) -> None:
    raw = _base_backtest_config()
    del raw["data"]["end_date"]
    with pytest.raises(ConfigError, match="end_date"):
        load_env_config(_write(tmp_path, raw))


def test_rejects_bad_date_format(tmp_path: Path) -> None:
    raw = _base_backtest_config()
    raw["data"]["start_date"] = "01/01/2025"
    with pytest.raises(ConfigError):
        load_env_config(_write(tmp_path, raw))


def test_rejects_end_before_start(tmp_path: Path) -> None:
    raw = _base_backtest_config()
    raw["data"]["start_date"] = "2025-03-01"
    raw["data"]["end_date"] = "2025-02-01"
    with pytest.raises(ConfigError, match="end_date"):
        load_env_config(_write(tmp_path, raw))
