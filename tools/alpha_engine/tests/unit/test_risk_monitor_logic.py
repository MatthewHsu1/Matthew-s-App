"""Pure-Python tests for RiskMonitorLogic.

The logic is fed:
  * `set_session_baseline(equity)` once at start
  * `on_equity(equity)` whenever the account-state event arrives
  * `tick(now, kill_file_exists)` on a clock cadence

Each call returns Optional[HaltReason]. Once any halt fires, all subsequent
calls return None (single-shot, idempotent — no auto un-halt).
"""
from __future__ import annotations

from datetime import datetime, time, timezone

from alpha_engine.risk.risk_monitor_logic import (
    HaltReason,
    RiskMonitorConfig,
    RiskMonitorLogic,
)


def _cfg(**overrides) -> RiskMonitorConfig:
    base = dict(
        max_daily_loss_usd=500.0,
        session_open_et=time(9, 30),
        session_close_et=time(16, 0),
    )
    base.update(overrides)
    return RiskMonitorConfig(**base)


def _utc(year, month, day, hour, minute) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_max_daily_loss_fires_when_equity_drop_exceeds_threshold() -> None:
    logic = RiskMonitorLogic(_cfg())
    logic.set_session_baseline(100_000.0)

    assert logic.on_equity(99_700.0) is None  # -300, under -500 threshold
    halt = logic.on_equity(99_400.0)
    assert halt is HaltReason.MAX_DAILY_LOSS


def test_max_daily_loss_idempotent_on_repeat_trigger() -> None:
    logic = RiskMonitorLogic(_cfg())
    logic.set_session_baseline(100_000.0)
    assert logic.on_equity(50_000.0) is HaltReason.MAX_DAILY_LOSS
    # Already halted — further drops do not re-fire.
    assert logic.on_equity(10_000.0) is None


def test_outside_market_hours_fires_before_open() -> None:
    cfg = _cfg(session_open_et=time(14, 30), session_close_et=time(21, 0))  # ≈ NYSE in UTC
    logic = RiskMonitorLogic(cfg)
    logic.set_session_baseline(100_000.0)
    # 14:00 UTC — before 14:30 open → halt.
    halt = logic.tick(now=_utc(2026, 5, 18, 14, 0), kill_file_exists=False)
    assert halt is HaltReason.OUTSIDE_MARKET_HOURS


def test_outside_market_hours_fires_after_close() -> None:
    cfg = _cfg(session_open_et=time(14, 30), session_close_et=time(21, 0))
    logic = RiskMonitorLogic(cfg)
    logic.set_session_baseline(100_000.0)
    halt = logic.tick(now=_utc(2026, 5, 18, 21, 30), kill_file_exists=False)
    assert halt is HaltReason.OUTSIDE_MARKET_HOURS


def test_within_market_hours_does_not_fire() -> None:
    cfg = _cfg(session_open_et=time(14, 30), session_close_et=time(21, 0))
    logic = RiskMonitorLogic(cfg)
    logic.set_session_baseline(100_000.0)
    halt = logic.tick(now=_utc(2026, 5, 18, 16, 0), kill_file_exists=False)
    assert halt is None


def test_kill_switch_file_fires_on_first_observation() -> None:
    cfg = _cfg(session_open_et=time(14, 30), session_close_et=time(21, 0))
    logic = RiskMonitorLogic(cfg)
    logic.set_session_baseline(100_000.0)
    halt = logic.tick(now=_utc(2026, 5, 18, 16, 0), kill_file_exists=True)
    assert halt is HaltReason.KILL_SWITCH_FILE


def test_kill_switch_does_not_unfire_when_file_is_removed() -> None:
    cfg = _cfg(session_open_et=time(14, 30), session_close_et=time(21, 0))
    logic = RiskMonitorLogic(cfg)
    logic.set_session_baseline(100_000.0)
    assert logic.tick(now=_utc(2026, 5, 18, 16, 0), kill_file_exists=True) is HaltReason.KILL_SWITCH_FILE
    # Operator deleted the file; the halt persists.
    assert logic.tick(now=_utc(2026, 5, 18, 16, 1), kill_file_exists=False) is None
    assert logic.halted is True
