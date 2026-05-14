from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_engine.cli_commands import env_new


def test_creates_env_dir_with_config_and_dirs(tmp_path: Path, monkeypatch):
    tmpl_dir = tmp_path / "templates"
    tmpl_dir.mkdir()
    template = {
        "env_name": "REPLACE",
        "mode": "backtest",
        "strategy": {"ref": "toy_buy_and_hold", "params": {"qty": 10, "buy_on_bar": 3}},
        "venue": {"id": "nasdaq_sim", "account_kind": "paper"},
        "data": {"live_source": "venue", "historical_source": "synthetic_fixture",
                 "instruments": ["MSFT.NASDAQ"]},
        "risk": {},
        "reporting": {"timezone": "UTC"},
    }
    (tmpl_dir / "backtest.json").write_text(json.dumps(template), encoding="utf-8")

    monkeypatch.setattr(env_new, "_templates_dir", lambda: tmpl_dir)

    envs_root = tmp_path / "envs"
    rc = env_new.run(envs_root=envs_root, name="my_env", template="backtest")
    assert rc == 0

    env_dir = envs_root / "my_env"
    assert (env_dir / "config.json").exists()
    assert (env_dir / "state").is_dir()
    assert (env_dir / "logs").is_dir()
    assert (env_dir / "reports").is_dir()
    assert (env_dir / "secrets.env").exists()

    cfg = json.loads((env_dir / "config.json").read_text())
    assert cfg["env_name"] == "my_env"


def test_refuses_to_overwrite_existing(tmp_path: Path, monkeypatch):
    tmpl_dir = tmp_path / "templates"
    tmpl_dir.mkdir()
    (tmpl_dir / "backtest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(env_new, "_templates_dir", lambda: tmpl_dir)

    envs_root = tmp_path / "envs"
    (envs_root / "my_env").mkdir(parents=True)
    rc = env_new.run(envs_root=envs_root, name="my_env", template="backtest")
    assert rc != 0
