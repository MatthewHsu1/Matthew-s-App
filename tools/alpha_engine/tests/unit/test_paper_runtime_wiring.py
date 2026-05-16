from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.config.paths import EnvPaths
from alpha_engine.engine.paper import (
    build_ibkr_client_configs,
    install_order_gate,
    install_kill_switch_poller,
)


def _cfg():
    return EnvConfig(
        env_name="test_env",
        mode=Mode.PAPER,
        strategy=StrategyConfig(ref="toy_buy_and_hold", params={}),
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
            historical_source="ibkr_historical",
            instruments=("AAPL.NASDAQ",),
            bar_spec="1-DAY-LAST",
            lookback_days=365,
        ),
        risk=RiskConfig(max_position_usd=10000.0, max_daily_loss_usd=500.0),
        reporting=ReportingConfig(timezone="UTC"),
    )


def test_build_ibkr_client_configs_returns_pair(monkeypatch):
    monkeypatch.setenv("IBKR_ACCOUNT_ID", "DU1")
    monkeypatch.setenv("IBKR_USERNAME", "u")
    monkeypatch.setenv("IBKR_PASSWORD", "p")
    data_cfg, exec_cfg = build_ibkr_client_configs(_cfg())
    # Pre-flight pinned ibg_port as the port field.
    assert getattr(data_cfg, "ibg_port") == 4002
    assert getattr(exec_cfg, "ibg_port") == 4002


def test_install_order_gate_subscribes_to_msgbus():
    bus = MagicMock()
    install_order_gate(
        msgbus=bus,
        risk_cfg=RiskConfig(max_position_usd=1000.0),
        risk_logger=MagicMock(),
        context_provider=lambda: MagicMock(),
    )
    bus.subscribe.assert_called_once()
    topic = bus.subscribe.call_args.kwargs.get("topic") or bus.subscribe.call_args.args[0]
    assert topic == "commands.trading.submit_order"


def test_install_kill_switch_poller_triggers_callbacks(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    callbacks = {"cancel": 0, "flatten": 0, "summary": 0}

    def cancel_all():
        callbacks["cancel"] += 1

    def flatten():
        callbacks["flatten"] += 1

    def write_summary(cause):
        callbacks["summary"] += 1

    poller = install_kill_switch_poller(
        killfile_path=killfile,
        cancel_all=cancel_all,
        flatten=flatten,
        write_summary=write_summary,
        flatten_on_halt=True,
    )
    # No killfile yet → tick is a no-op.
    poller.tick()
    assert callbacks == {"cancel": 0, "flatten": 0, "summary": 0}

    killfile.touch()
    poller.tick()
    assert callbacks == {"cancel": 1, "flatten": 1, "summary": 1}

    # Subsequent ticks are idempotent (don't re-fire).
    poller.tick()
    assert callbacks == {"cancel": 1, "flatten": 1, "summary": 1}
