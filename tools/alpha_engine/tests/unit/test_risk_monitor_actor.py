"""Unit tests for RiskMonitorActor wiring.

Tactic: construct the actor, inject fakes for set_trading_state / log /
the kill-file path. The actor's logic-class delegation is exercised
fully in test_risk_monitor_logic.py — here we just verify wiring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from nautilus_trader.model.enums import TradingState

from alpha_engine.risk.risk_monitor_actor import (
    RiskMonitorActor,
    RiskMonitorActorConfig,
)


@pytest.fixture
def actor() -> RiskMonitorActor:
    cfg = RiskMonitorActorConfig(
        max_daily_loss_usd=500.0,
        session_open_et="14:30",
        session_close_et="21:00",
        kill_switch_path="/tmp/nonexistent.flag",
        tick_interval_seconds=1.0,
    )
    inst = RiskMonitorActor(cfg)
    # set_trading_state is writable on Actor subclass instances.
    inst._fake_set_state = MagicMock()
    inst.set_trading_state = inst._fake_set_state  # type: ignore[assignment]
    # log is Cython-sealed — inject fake at the _emit_warning Python seam instead.
    inst._fake_emit_warning = MagicMock()
    inst._emit_warning = inst._fake_emit_warning  # type: ignore[assignment]
    return inst


def test_on_equity_below_threshold_halts(actor: RiskMonitorActor) -> None:
    actor.set_baseline_equity(100_000.0)
    actor.handle_equity(99_400.0)  # -600 vs 500 threshold
    actor._fake_set_state.assert_called_once_with(TradingState.HALTED)


def test_on_equity_above_threshold_does_not_halt(actor: RiskMonitorActor) -> None:
    actor.set_baseline_equity(100_000.0)
    actor.handle_equity(99_700.0)
    actor._fake_set_state.assert_not_called()


def test_tick_outside_market_hours_halts(actor: RiskMonitorActor, monkeypatch) -> None:
    # 22:00 UTC = past 21:00 close.
    monkeypatch.setattr(
        "alpha_engine.risk.risk_monitor_actor._now_utc",
        lambda: datetime(2026, 5, 18, 22, 0, tzinfo=timezone.utc),
    )
    actor.tick()
    actor._fake_set_state.assert_called_once_with(TradingState.HALTED)


def test_tick_inside_market_hours_no_action(actor: RiskMonitorActor, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha_engine.risk.risk_monitor_actor._now_utc",
        lambda: datetime(2026, 5, 18, 16, 0, tzinfo=timezone.utc),
    )
    actor.tick()
    actor._fake_set_state.assert_not_called()


def test_tick_kill_switch_file_halts(tmp_path, monkeypatch) -> None:
    killfile = tmp_path / "kill.flag"
    killfile.write_text("")
    cfg = RiskMonitorActorConfig(
        max_daily_loss_usd=500.0,
        session_open_et="14:30",
        session_close_et="21:00",
        kill_switch_path=str(killfile),
        tick_interval_seconds=1.0,
    )
    actor = RiskMonitorActor(cfg)
    # set_trading_state is writable on Actor subclass instances.
    actor._fake_set_state = MagicMock()
    actor.set_trading_state = actor._fake_set_state  # type: ignore[assignment]
    # log is Cython-sealed — inject fake at the _emit_warning Python seam instead.
    actor._fake_emit_warning = MagicMock()
    actor._emit_warning = actor._fake_emit_warning  # type: ignore[assignment]

    monkeypatch.setattr(
        "alpha_engine.risk.risk_monitor_actor._now_utc",
        lambda: datetime(2026, 5, 18, 16, 0, tzinfo=timezone.utc),
    )
    actor.tick()
    actor._fake_set_state.assert_called_once_with(TradingState.HALTED)


def test_halt_is_idempotent_across_multiple_triggers(actor: RiskMonitorActor) -> None:
    actor.set_baseline_equity(100_000.0)
    actor.handle_equity(50_000.0)
    actor.handle_equity(10_000.0)
    actor.handle_equity(0.0)
    assert actor._fake_set_state.call_count == 1
