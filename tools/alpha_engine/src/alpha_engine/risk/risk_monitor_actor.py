"""Nautilus Actor that owns the trading-state halt decisions.

Three halt conditions, all routed through `RiskMonitorLogic`:
  1. Account equity drops `max_daily_loss_usd` below session start →
     `set_trading_state(HALTED)` with reason `max_daily_loss`.
  2. Wall-clock time outside `[session_open_et, session_close_et]` →
     `set_trading_state(HALTED)` with reason `outside_market_hours`.
  3. Kill-switch file present at `kill_switch_path` →
     `set_trading_state(HALTED)` with reason `kill_switch_file`.

Halts are one-way for the session; operator restarts to recover.

This module is intentionally thin: detection is in `RiskMonitorLogic`,
the actor only wires Nautilus events and the `set_trading_state` call.
Live wiring of account-state subscription + clock timer is deferred to
PR 3 (env runner scripts). The pure logic is covered by
`test_risk_monitor_logic.py`; this module's tests cover the actor's
delegation contract.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path

from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.model.enums import TradingState

from alpha_engine.risk.risk_monitor_logic import (
    HaltReason,
    RiskMonitorConfig,
    RiskMonitorLogic,
)


def _now_utc() -> datetime:
    """Indirection so unit tests can monkeypatch the wall clock."""
    return datetime.now(tz=timezone.utc)


def _parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


class RiskMonitorActorConfig(ActorConfig):
    max_daily_loss_usd: float
    session_open_et: str   # "HH:MM" in UTC (config files state explicit UTC offsets)
    session_close_et: str  # "HH:MM" in UTC
    kill_switch_path: str
    tick_interval_seconds: float = 1.0


class RiskMonitorActor(Actor):
    def __init__(self, config: RiskMonitorActorConfig) -> None:
        super().__init__(config=config)
        self._cfg = config
        self._kill_path = Path(config.kill_switch_path)
        self._logic = RiskMonitorLogic(
            RiskMonitorConfig(
                max_daily_loss_usd=config.max_daily_loss_usd,
                session_open_et=_parse_hhmm(config.session_open_et),
                session_close_et=_parse_hhmm(config.session_close_et),
            )
        )

    def set_baseline_equity(self, equity: float) -> None:
        self._logic.set_session_baseline(equity)

    def handle_equity(self, equity: float) -> None:
        reason = self._logic.on_equity(equity)
        if reason is not None:
            self._halt(reason)

    def tick(self) -> None:
        reason = self._logic.tick(now=_now_utc(), kill_file_exists=self._kill_path.exists())
        if reason is not None:
            self._halt(reason)

    def _halt(self, reason: HaltReason) -> None:
        self._emit_warning(f"risk_halt: {reason.name.lower()}")
        self._set_halted()

    # ----- Cython-sealed-attribute seams (see Tasks 5/7/8 for pattern) -----
    def _emit_warning(self, message: str) -> None:
        """Wraps `self.log.warning(...)` — `log` is Cython-sealed on Actor."""
        self.log.warning(message)

    def _set_halted(self) -> None:
        """Wraps `set_trading_state(TradingState.HALTED)` — `set_trading_state`
        is writable on Actor subclass instances so tests can inject directly,
        but this seam is retained for clarity and future-proofing."""
        self.set_trading_state(TradingState.HALTED)
