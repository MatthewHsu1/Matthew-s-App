from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.control.boot_guards import BootRefusedError
from alpha_engine.engine.paper import run_paper


class _StubNode:
    def __init__(self, data_cfg, exec_cfg):
        self.data_cfg = data_cfg
        self.exec_cfg = exec_cfg
        self.run_called = False

    def run(self):
        self.run_called = True

    def stop(self):
        pass


def _cfg():
    return EnvConfig(
        env_name="paper_test",
        mode=Mode.PAPER,
        strategy=StrategyConfig(ref="toy_buy_and_hold"),
        venue=VenueConfig(
            id="ibkr",
            account_kind="paper",
            gateway_host="host-gateway",
            gateway_port_paper=4002,
            gateway_port_live=4001,
            account_id_env="IBKR_ACCOUNT_ID",
            username_env="IBKR_USERNAME",
            password_env="IBKR_PASSWORD",
        ),
        data=DataConfig(
            live_source="ibkr",
            historical_source="synthetic_fixture",
            instruments=("AAPL.NASDAQ",),
            bar_spec="1-DAY-LAST",
            lookback_days=30,
        ),
        risk=RiskConfig(max_position_usd=10000.0, max_daily_loss_usd=500.0),
        reporting=ReportingConfig(timezone="UTC"),
    )


def test_run_paper_writes_last_run_and_invokes_node(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "DU1")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")

    paths = EnvPaths(envs_root=tmp_path, env_name="paper_test")
    paths.ensure_dirs()

    node_holder: list[_StubNode] = []

    def factory(data_cfg, exec_cfg):
        n = _StubNode(data_cfg, exec_cfg)
        node_holder.append(n)
        return n

    result = run_paper(cfg=_cfg(), paths=paths, trading_node_factory=factory)
    assert result.run_id

    last_run_data = json.loads(paths.last_run_path.read_text())
    assert last_run_data["pid"] == os.getpid()
    assert last_run_data["mode"] == "paper"
    assert last_run_data["env_name"] == "paper_test"
    assert last_run_data["run_id"] == result.run_id

    assert len(node_holder) == 1
    assert node_holder[0].data_cfg is not None
    assert node_holder[0].exec_cfg is not None


def test_run_paper_refuses_when_killswitch_active(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "DU1")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")

    paths = EnvPaths(envs_root=tmp_path, env_name="paper_test")
    paths.ensure_dirs()
    paths.kill_switch_path.touch()

    with pytest.raises(BootRefusedError, match="kill-switch"):
        run_paper(cfg=_cfg(), paths=paths, trading_node_factory=lambda d, e: _StubNode(d, e))
